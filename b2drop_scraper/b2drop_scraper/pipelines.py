# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import sys
import os
import time
import hashlib
from datetime import datetime
from itemadapter import ItemAdapter

# Adiciona o diretório pai ao path para importar nossos módulos
current_dir = os.path.dirname(__file__)
parent_dir = os.path.join(current_dir, '..', '..')
sys.path.append(parent_dir)

try:
    from cloudflare_storage_fixed import CloudflareStorage
except ImportError:
    # Fallback para quando executado diretamente
    import sys
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, project_root)
    from cloudflare_storage_fixed import CloudflareStorage
from .items import B2DropProductItem


class ValidationPipeline:
    """Pipeline para validar dados dos items antes do processamento"""
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Validações essenciais
        if not adapter.get('produto'):
            spider.logger.warning(f"Item sem nome de produto será descartado: {adapter}")
            raise DropItem("Nome do produto é obrigatório")
        
        # Limpa e padroniza preços
        preco = adapter.get('preco', 0)
        if isinstance(preco, str):
            try:
                adapter['preco'] = float(preco.replace(',', '.'))
            except:
                adapter['preco'] = 0.0
        
        # Garante campos obrigatórios
        adapter.setdefault('categoria', 'Outros')
        adapter.setdefault('disponibilidade', 'Disponível')
        adapter.setdefault('scraped_at', datetime.now().isoformat())
        
        return item


class DuplicationFilterPipeline:
    """Pipeline para filtrar produtos duplicados"""
    
    def __init__(self):
        self.ids_seen = set()
        self.products_filtered = 0
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Gera ID único baseado em produto + URL
        unique_id = self.generate_unique_id(adapter)
        
        if unique_id in self.ids_seen:
            self.products_filtered += 1
            spider.logger.debug(f"Item duplicado filtrado: {adapter.get('produto')}")
            raise DropItem(f"Item duplicado: {unique_id}")
        
        self.ids_seen.add(unique_id)
        adapter['hash_produto'] = unique_id
        
        return item
    
    def generate_unique_id(self, adapter):
        """Gera ID único para o produto"""
        produto = adapter.get('produto', '')
        url = adapter.get('url_produto', '')
        cor = adapter.get('cor', '')
        tamanho = adapter.get('tamanho', '')
        
        content = f"{produto}_{url}_{cor}_{tamanho}".lower()
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def close_spider(self, spider):
        spider.logger.info(f"Pipeline DuplicationFilter: {self.products_filtered} duplicados filtrados")


class CloudflarePipeline:
    """Pipeline principal para enviar dados para Cloudflare KV + R2"""
    
    def __init__(self):
        self.storage = None
        self.products_processed = 0
        self.products_uploaded = 0
        self.products_failed = 0
        self.images_uploaded = 0
    
    def open_spider(self, spider):
        """Inicializa conexão com Cloudflare quando spider inicia"""
        try:
            self.storage = CloudflareStorage()
            
            # Testa conectividade
            if not self.storage.init_r2_bucket():
                spider.logger.error("Falha ao inicializar bucket R2")
                raise Exception("Não foi possível conectar ao Cloudflare")
            
            spider.logger.info("✅ Pipeline Cloudflare inicializada com sucesso")
            
        except Exception as e:
            spider.logger.error(f"❌ Erro ao inicializar pipeline Cloudflare: {e}")
            raise
    
    def process_item(self, item, spider):
        """Processa cada item enviando para Cloudflare"""
        adapter = ItemAdapter(item)
        self.products_processed += 1
        
        try:
            # Prepara dados para o Cloudflare
            cloudflare_data = self.prepare_cloudflare_data(adapter)
            
            # Upload da imagem para R2 (se disponível)
            if adapter.get('imagem_original'):
                r2_url = self.upload_image_to_r2(
                    adapter['imagem_original'], 
                    adapter['produto'],
                    spider
                )
                if r2_url:
                    cloudflare_data['imagem_r2'] = r2_url
                    self.images_uploaded += 1
            
            # Armazena produto no KV
            success = self.storage.store_product(cloudflare_data)
            
            if success:
                self.products_uploaded += 1
                spider.logger.debug(f"✅ Produto armazenado: {adapter['produto']}")
            else:
                self.products_failed += 1
                spider.logger.warning(f"❌ Falha ao armazenar: {adapter['produto']}")
            
            # Log de progresso a cada 10 produtos
            if self.products_processed % 10 == 0:
                spider.logger.info(
                    f"📊 Progresso: {self.products_processed} processados, "
                    f"{self.products_uploaded} enviados, "
                    f"{self.products_failed} falhas"
                )
            
            return item
            
        except Exception as e:
            self.products_failed += 1
            spider.logger.error(f"❌ Erro ao processar item {adapter.get('produto', 'N/A')}: {e}")
            return item  # Retorna item mesmo com erro para não interromper pipeline
    
    def prepare_cloudflare_data(self, adapter):
        """Converte item Scrapy para formato Cloudflare"""
        return {
            'product_id': adapter.get('hash_produto') or self.generate_product_id(),
            'produto': adapter['produto'],
            'descricao': adapter.get('descricao', ''),
            'preco': float(adapter.get('preco', 0)),
            'categoria': adapter.get('categoria', 'Outros'),
            'cor': adapter.get('cor', ''),
            'tamanho': adapter.get('tamanho', ''),
            'imagem_original': adapter.get('imagem_original', ''),
            'imagem_r2': None,  # Será preenchido se upload bem-sucedido
            'url_produto': adapter.get('url_produto', ''),
            'disponibilidade': adapter.get('disponibilidade', 'Disponível'),
            'produto_base': adapter.get('produto_base', ''),
            'total_variacoes': adapter.get('total_variacoes', 1),
            'scraped_at': adapter.get('scraped_at'),
            'created_at': datetime.now().isoformat()
        }
    
    def upload_image_to_r2(self, image_url, product_name, spider):
        """Upload de imagem para Cloudflare R2"""
        try:
            if not image_url:
                return None
            
            r2_url = self.storage.upload_image(image_url, product_name)
            
            if r2_url:
                spider.logger.debug(f"🖼️ Imagem enviada para R2: {product_name}")
                return r2_url
            else:
                spider.logger.warning(f"⚠️ Falha no upload da imagem: {product_name}")
                return None
                
        except Exception as e:
            spider.logger.error(f"❌ Erro no upload da imagem {product_name}: {e}")
            return None
    
    def generate_product_id(self):
        """Gera ID único se não fornecido"""
        timestamp = int(time.time())
        return f"scrapy_{timestamp}_{hashlib.md5(str(timestamp).encode()).hexdigest()[:8]}"
    
    def close_spider(self, spider):
        """Relatório final quando spider termina"""
        spider.logger.info("="*60)
        spider.logger.info("📊 RELATÓRIO FINAL - PIPELINE CLOUDFLARE")
        spider.logger.info("="*60)
        spider.logger.info(f"📦 Produtos processados: {self.products_processed}")
        spider.logger.info(f"✅ Produtos enviados: {self.products_uploaded}")
        spider.logger.info(f"❌ Produtos com falha: {self.products_failed}")
        spider.logger.info(f"🖼️ Imagens enviadas: {self.images_uploaded}")
        
        success_rate = (self.products_uploaded / self.products_processed * 100) if self.products_processed > 0 else 0
        spider.logger.info(f"📈 Taxa de sucesso: {success_rate:.1f}%")
        spider.logger.info("="*60)


class DropItem(Exception):
    """Exception para descartar items"""
    pass