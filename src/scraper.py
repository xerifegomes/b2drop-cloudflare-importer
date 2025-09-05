"""
Scraper para extrair dados do catálogo B2Drop
Implementa extração robusta com tratamento de erros
"""

import time
import re
import uuid
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from loguru import logger
from tqdm import tqdm

from .config import settings
from .models import Product, ProductVariation


class B2DropScraper:
    """Scraper principal para o catálogo B2Drop"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': settings.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.base_url = settings.b2drop_base_url
        self.catalog_url = settings.b2drop_catalog_url
        
    def _make_request(self, url: str, retries: int = None) -> Optional[requests.Response]:
        """Faz requisição com retry automático"""
        if retries is None:
            retries = settings.max_retries
            
        for attempt in range(retries + 1):
            try:
                logger.info(f"Fazendo requisição para: {url} (tentativa {attempt + 1})")
                response = self.session.get(
                    url, 
                    timeout=settings.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # Delay entre requisições
                if settings.request_delay > 0:
                    time.sleep(settings.request_delay)
                    
                return response
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro na requisição (tentativa {attempt + 1}): {e}")
                if attempt < retries:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    logger.error(f"Falha após {retries + 1} tentativas: {e}")
                    return None
                    
        return None
    
    def _extract_price(self, price_text: str) -> float:
        """Extrai preço do texto"""
        if not price_text:
            return 0.0
            
        # Remove caracteres não numéricos exceto vírgula e ponto
        price_clean = re.sub(r'[^\d,.]', '', price_text)
        
        # Substitui vírgula por ponto para conversão
        price_clean = price_clean.replace(',', '.')
        
        try:
            return float(price_clean)
        except ValueError:
            logger.warning(f"Não foi possível extrair preço de: {price_text}")
            return 0.0
    
    def _extract_product_info(self, product_element) -> Optional[Dict[str, Any]]:
        """Extrai informações de um elemento de produto"""
        try:
            # Nome do produto
            name_element = product_element.find('h5') or product_element.find('h4') or product_element.find('h3')
            if not name_element:
                return None
                
            product_name = name_element.get_text(strip=True)
            if not product_name:
                return None
            
            # Preço
            price_element = product_element.find(text=re.compile(r'R\$\s*\d+'))
            if not price_element:
                return None
                
            price_text = price_element.strip()
            price = self._extract_price(price_text)
            
            # Imagem
            img_element = product_element.find('img')
            image_url = None
            if img_element:
                img_src = img_element.get('src') or img_element.get('data-src')
                if img_src:
                    image_url = urljoin(self.base_url, img_src)
            
            # Descrição - procura por diferentes elementos que podem conter descrição
            description = self._extract_description(product_element)
            
            # Link do produto
            link_element = product_element.find('a')
            product_url = None
            if link_element:
                href = link_element.get('href')
                if href:
                    product_url = urljoin(self.base_url, href)
            
            return {
                'name': product_name,
                'description': description,
                'price': price,
                'image_url': image_url,
                'product_url': product_url,
                'raw_html': str(product_element)
            }
            
        except Exception as e:
            logger.error(f"Erro ao extrair informações do produto: {e}")
            return None
    
    def _extract_description(self, product_element) -> Optional[str]:
        """Extrai descrição do produto de diferentes elementos possíveis"""
        try:
            # Procura por diferentes seletores que podem conter descrição
            description_selectors = [
                'p',  # Parágrafo
                'div[class*="description"]',  # Div com classe description
                'div[class*="desc"]',  # Div com classe desc
                'span[class*="description"]',  # Span com classe description
                'div[class*="text"]',  # Div com classe text
                'div[class*="info"]',  # Div com classe info
                'div[class*="details"]',  # Div com classe details
                '.product-description',  # Classe específica
                '.product-desc',  # Classe específica
                '.product-info',  # Classe específica
            ]
            
            for selector in description_selectors:
                desc_element = product_element.select_one(selector)
                if desc_element:
                    desc_text = desc_element.get_text(strip=True)
                    # Filtra descrições muito curtas ou que são apenas preços
                    if len(desc_text) > 10 and not re.match(r'^R\$\s*\d+', desc_text):
                        return desc_text
            
            # Se não encontrou descrição específica, usa o nome como descrição
            name_element = product_element.find('h5') or product_element.find('h4') or product_element.find('h3')
            if name_element:
                return name_element.get_text(strip=True)
            
            return None
            
        except Exception as e:
            logger.warning(f"Erro ao extrair descrição: {e}")
            return None
    
    def _categorize_product(self, product_name: str) -> str:
        """Categoriza produto baseado no nome"""
        name_lower = product_name.lower()
        
        # Categorias baseadas em palavras-chave
        categories = {
            'Eletrônicos': ['cabo', 'carregador', 'fone', 'câmera', 'drone', 'walkie', 'microfone', 'led', 'wifi'],
            'Casa e Organização': ['suporte', 'organizador', 'sapateira', 'guarda-roupa', 'dispenser', 'recipiente'],
            'Saúde e Bem-estar': ['ortopédica', 'compressão', 'exercício', 'massagem', 'terapêutica', 'fisioterapia'],
            'Pet Shop': ['pet', 'cachorro', 'gato', 'coleira', 'brinquedo', 'escova'],
            'Moda e Acessórios': ['short', 'mochila', 'maleta', 'pulseira', 'cinto', 'copo'],
            'Cozinha': ['faca', 'utensílio', 'sanduicheira', 'fritadeira', 'air fryer', 'kit'],
            'Limpeza': ['esfregão', 'aspirador', 'limpador', 'vassoura', 'rodo'],
            'Esportes': ['yoga', 'ginástica', 'exercício', 'step', 'elástico', 'bandagem']
        }
        
        for category, keywords in categories.items():
            if any(keyword in name_lower for keyword in keywords):
                return category
                
        return 'Outros'
    
    def _group_variations(self, products: List[Dict[str, Any]]) -> List[Product]:
        """Agrupa produtos em variações"""
        grouped_products = {}
        
        for product_data in products:
            name = product_data['name']
            description = product_data.get('description', '')
            price = product_data['price']
            image_url = product_data.get('image_url')
            
            # Tenta identificar o nome base removendo variações de cor/tamanho
            base_name = self._extract_base_name(name)
            
            if base_name not in grouped_products:
                # Cria novo produto
                product_id = str(uuid.uuid4())
                category = self._categorize_product(name)
                
                product = Product(
                    product_id=product_id,
                    base_name=base_name,
                    category=category,
                    description=description,
                    min_price=price,  # Inicializa com o preço da primeira variação
                    max_price=price
                )
                grouped_products[base_name] = product
            
            # Adiciona variação
            variation_id = str(uuid.uuid4())
            variation = ProductVariation(
                variation_id=variation_id,
                name=name,
                price=price,
                image_url=image_url,
                color=self._extract_color(name),
                size=self._extract_size(name)
            )
            
            grouped_products[base_name].add_variation(variation)
        
        return list(grouped_products.values())
    
    def _extract_base_name(self, name: str) -> str:
        """Extrai nome base removendo variações de cor/tamanho"""
        # Remove cores comuns
        colors = ['preto', 'branco', 'azul', 'rosa', 'verde', 'cinza', 'amarelo', 'lilás', 'vinho', 'bege', 'marrom']
        base_name = name
        
        for color in colors:
            # Remove cor do final do nome
            base_name = re.sub(rf'\s+{color}\s*$', '', base_name, flags=re.IGNORECASE)
            # Remove cor do meio do nome
            base_name = re.sub(rf'\s+{color}\s+', ' ', base_name, flags=re.IGNORECASE)
        
        # Remove tamanhos
        sizes = ['m', 'g', 'gg', 'p', 'pp', 'ppp', 'xs', 's', 'l', 'xl', 'xxl']
        for size in sizes:
            base_name = re.sub(rf'\s+{size}\s*$', '', base_name, flags=re.IGNORECASE)
            base_name = re.sub(rf'\s+{size}\s+', ' ', base_name, flags=re.IGNORECASE)
        
        return base_name.strip()
    
    def _extract_color(self, name: str) -> Optional[str]:
        """Extrai cor do nome do produto"""
        colors = ['preto', 'branco', 'azul', 'rosa', 'verde', 'cinza', 'amarelo', 'lilás', 'vinho', 'bege', 'marrom']
        name_lower = name.lower()
        
        for color in colors:
            if color in name_lower:
                return color.title()
        return None
    
    def _extract_size(self, name: str) -> Optional[str]:
        """Extrai tamanho do nome do produto"""
        sizes = ['m', 'g', 'gg', 'p', 'pp', 'ppp', 'xs', 's', 'l', 'xl', 'xxl']
        name_lower = name.lower()
        
        for size in sizes:
            if size in name_lower:
                return size.upper()
        return None
    
    def scrape_catalog(self) -> List[Product]:
        """Scrapa todo o catálogo"""
        logger.info("Iniciando scraping do catálogo B2Drop")
        
        # Faz requisição inicial
        response = self._make_request(self.catalog_url)
        if not response:
            logger.error("Falha ao acessar o catálogo")
            return []
        
        # Parse do HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Encontra elementos de produtos
        # Procura por diferentes padrões de estrutura
        product_selectors = [
            'div[class*="product"]',
            'div[class*="item"]',
            'div[class*="card"]',
            '.product-item',
            '.product-card',
            '.catalog-item'
        ]
        
        product_elements = []
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                logger.info(f"Encontrados {len(elements)} produtos com seletor: {selector}")
                product_elements = elements
                break
        
        if not product_elements:
            logger.warning("Nenhum produto encontrado com os seletores padrão")
            # Fallback: procura por qualquer elemento que contenha preço
            product_elements = soup.find_all(text=re.compile(r'R\$\s*\d+'))
            product_elements = [elem.parent for elem in product_elements if elem.parent]
        
        logger.info(f"Total de elementos encontrados: {len(product_elements)}")
        
        # Extrai informações dos produtos
        products_data = []
        for element in tqdm(product_elements, desc="Extraindo produtos"):
            product_info = self._extract_product_info(element)
            if product_info:
                products_data.append(product_info)
        
        logger.info(f"Produtos extraídos: {len(products_data)}")
        
        # Agrupa em variações
        grouped_products = self._group_variations(products_data)
        
        logger.info(f"Produtos agrupados: {len(grouped_products)}")
        logger.info("Scraping concluído com sucesso")
        
        return grouped_products
