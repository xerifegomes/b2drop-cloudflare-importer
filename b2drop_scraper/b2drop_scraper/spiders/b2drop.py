import scrapy
import time
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse
from scrapy.loader import ItemLoader

from ..items import B2DropProductItem, B2DropCategoryItem


class B2dropSpider(scrapy.Spider):
    name = "b2drop"
    allowed_domains = ["app.sistemab2drop.com.br"]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.5,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = time.time()
        self.products_scraped = 0
        self.categories_found = set()
        
    def start_requests(self):
        """URLs iniciais para começar o scraping"""
        urls = [
            'https://app.sistemab2drop.com.br/products',
            'https://app.sistemab2drop.com.br/catalog',
        ]
        
        for url in urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_catalog,
                meta={'dont_cache': True}
            )
    
    def parse_catalog(self, response):
        """Extrai produtos da página de catálogo"""
        self.logger.info(f"Processando catálogo: {response.url}")
        
        # Seleciona produtos na página
        product_selectors = [
            '.product-item',
            '.produto-card', 
            '.card-produto',
            'div[data-product-id]',
            '.product-container',
        ]
        
        products = []
        for selector in product_selectors:
            products = response.css(selector)
            if products:
                self.logger.info(f"Encontrados {len(products)} produtos usando seletor: {selector}")
                break
        
        if not products:
            # Fallback: busca por links que contenham 'product'
            products = response.css('a[href*="product"]').getall()
            self.logger.warning(f"Usando fallback: encontrados {len(products)} links de produtos")
        
        # Processa cada produto
        for product in products:
            yield self.parse_product_card(product, response)
        
        # Busca próxima página
        next_page = self.get_next_page_url(response)
        if next_page:
            yield response.follow(
                next_page, 
                callback=self.parse_catalog,
                meta={'dont_cache': True}
            )
    
    def parse_product_card(self, product_element, response):
        """Extrai dados de um card de produto"""
        loader = ItemLoader(item=B2DropProductItem(), selector=product_element)
        
        try:
            # Extrai informações básicas do card
            loader.add_css('produto', '.product-title, .produto-nome, h3, .title')
            loader.add_css('preco', '.price, .preco, .valor')
            loader.add_css('preco_promocional', '.sale-price, .preco-promocional')
            loader.add_css('imagem_original', 'img::attr(src)')
            
            # URL do produto para detalhes
            product_url = product_element.css('a::attr(href)').get()
            if product_url:
                product_url = urljoin(response.url, product_url)
                loader.add_value('url_produto', product_url)
                
                # Segue para página de detalhes
                return response.follow(
                    product_url,
                    callback=self.parse_product_detail,
                    meta={'loader': loader}
                )
        
        except Exception as e:
            self.logger.error(f"Erro ao processar card de produto: {e}")
            return None
    
    def parse_product_detail(self, response):
        """Extrai detalhes completos do produto"""
        loader = response.meta.get('loader')
        
        try:
            # Informações detalhadas
            loader.add_css('descricao', '.product-description, .descricao-produto, .description')
            loader.add_css('categoria', '.breadcrumb li:last-child, .categoria, .category')
            loader.add_css('disponibilidade', '.stock-status, .disponibilidade, .availability')
            loader.add_css('sku', '.sku, .codigo-produto')
            
            # Variações (cor, tamanho)
            loader.add_css('cor', '.color-option.selected, .cor-selecionada, [data-color]')
            loader.add_css('tamanho', '.size-option.selected, .tamanho-selecionado, [data-size]')
            
            # Imagens adicionais
            additional_images = response.css('.product-gallery img::attr(src), .galeria-produto img::attr(src)').getall()
            if additional_images:
                loader.add_value('imagens_adicionais', additional_images)
            
            # Metadados
            loader.add_value('scraped_at', datetime.now().isoformat())
            loader.add_value('url_produto', response.url)
            
            # Gera hash único do produto
            product_hash = self.generate_product_hash(response.url, loader.get_output_value('produto'))
            loader.add_value('hash_produto', product_hash)
            
            # Extrai ID do produto da URL
            loader.add_value('product_id', response.url)
            
            # Detecta variações e produto base
            self.process_variations(loader, response)
            
            self.products_scraped += 1
            
            # Adiciona categoria ao set
            categoria = loader.get_output_value('categoria')
            if categoria:
                self.categories_found.add(categoria)
            
            item = loader.load_item()
            self.logger.info(f"Produto extraído: {item.get('produto', 'N/A')}")
            
            return item
            
        except Exception as e:
            self.logger.error(f"Erro ao processar detalhes do produto {response.url}: {e}")
            return None
    
    def process_variations(self, loader, response):
        """Processa variações do produto (cores, tamanhos)"""
        try:
            # Detecta produto base removendo variações
            produto = loader.get_output_value('produto') or ''
            cor = loader.get_output_value('cor') or ''
            tamanho = loader.get_output_value('tamanho') or ''
            
            produto_base = produto
            for variacao in [cor, tamanho]:
                if variacao and variacao.lower() in produto.lower():
                    produto_base = produto.replace(f" {variacao}", "").replace(f"- {variacao}", "").strip()
            
            loader.add_value('produto_base', produto_base)
            
            # Conta variações (aproximação baseada em opções disponíveis)
            color_options = response.css('.color-option, .cor-opcao, [data-color]').getall()
            size_options = response.css('.size-option, .tamanho-opcao, [data-size]').getall()
            
            total_variations = max(len(color_options), len(size_options), 1)
            loader.add_value('total_variacoes', total_variations)
            
        except Exception as e:
            self.logger.warning(f"Erro ao processar variações: {e}")
    
    def get_next_page_url(self, response):
        """Encontra URL da próxima página"""
        next_selectors = [
            '.pagination .next::attr(href)',
            '.paginacao .proximo::attr(href)',
            'a[rel="next"]::attr(href)',
            '.page-numbers .next::attr(href)'
        ]
        
        for selector in next_selectors:
            next_url = response.css(selector).get()
            if next_url:
                return urljoin(response.url, next_url)
        
        return None
    
    def generate_product_hash(self, url, name):
        """Gera hash único para o produto"""
        content = f"{url}_{name}_{datetime.now().date()}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def closed(self, reason):
        """Callback executado quando spider termina"""
        execution_time = time.time() - self.start_time
        
        self.logger.info(f"Spider finalizado. Motivo: {reason}")
        self.logger.info(f"Produtos processados: {self.products_scraped}")
        self.logger.info(f"Categorias encontradas: {len(self.categories_found)}")
        self.logger.info(f"Tempo de execução: {execution_time:.2f}s")
        
        # Opcionalmente, pode gerar item de estatísticas
        # stats_item = B2DropStatsItem()
        # stats_item['total_produtos'] = self.products_scraped
        # yield stats_item