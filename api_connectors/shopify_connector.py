#!/usr/bin/env python3
"""
Shopify API Connector
Integração com Shopify Admin API para coleta de produtos das lojas configuradas
"""

import os
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv('.env.apis')


class ShopifyConnector:
    """Conector para Shopify Admin API"""
    
    def __init__(self):
        # Configurações das lojas Shopify
        self.stores = [
            {
                'name': 'Store 1',
                'domain': os.getenv('SHOPIFY_STORE_1'),
                'admin_token': os.getenv('SHOPIFY_ADMIN_TOKEN_1'),
                'api_key': os.getenv('SHOPIFY_API_KEY_1'),
                'api_secret': os.getenv('SHOPIFY_API_SECRET_1')
            },
            {
                'name': 'NuvexTester',
                'domain': os.getenv('SHOPIFY_STORE_2'), 
                'admin_token': os.getenv('SHOPIFY_ADMIN_TOKEN_2'),
                'api_key': os.getenv('SHOPIFY_API_KEY_2'),
                'api_secret': os.getenv('SHOPIFY_API_SECRET_2')
            }
        ]
        
        self.session = requests.Session()
        self.rate_limit_delay = 0.5  # Shopify permite 2 req/sec
        
        logger.info("🛍️ Shopify Connector inicializado")
        logger.info(f"🏪 Lojas configuradas: {len([s for s in self.stores if s['domain']])}")
    
    def _make_request(self, store: Dict, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Faz requisição para Shopify Admin API"""
        try:
            if not store['domain'] or not store['admin_token']:
                logger.warning(f"⚠️ Store {store['name']} sem configuração válida")
                return None
            
            url = f"https://{store['domain']}/admin/api/2023-10{endpoint}"
            
            headers = {
                'X-Shopify-Access-Token': store['admin_token'],
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            logger.debug(f"📞 Shopify {store['name']} Request: {endpoint}")
            
            response = self.session.get(url, headers=headers, params=params)
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning(f"⚠️ Rate limit {store['name']} - aguardando...")
                time.sleep(2)
                return self._make_request(store, endpoint, params)
            else:
                logger.error(f"❌ Shopify {store['name']} Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na requisição {store['name']}: {e}")
            return None
    
    def get_all_products(self, limit_per_store: int = 50) -> List[Dict]:
        """Obtém produtos de todas as lojas Shopify"""
        try:
            all_products = []
            
            for store in self.stores:
                if not store['domain']:
                    continue
                    
                logger.info(f"🔍 Buscando produtos da loja: {store['name']}")
                
                store_products = self.get_store_products(store, limit_per_store)
                all_products.extend(store_products)
                
                logger.info(f"✅ {store['name']}: {len(store_products)} produtos coletados")
            
            logger.info(f"✅ Shopify Total: {len(all_products)} produtos de todas as lojas")
            return all_products
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar produtos Shopify: {e}")
            return []
    
    def get_store_products(self, store: Dict, limit: int = 50) -> List[Dict]:
        """Obtém produtos de uma loja específica"""
        try:
            products = []
            page_info = None
            collected = 0
            
            while collected < limit:
                params = {
                    'limit': min(50, limit - collected),  # Máximo 50 por página
                    'status': 'active'
                }
                
                # Paginação cursor-based
                if page_info:
                    params['page_info'] = page_info
                
                result = self._make_request(store, '/products.json', params)
                
                if not result or 'products' not in result:
                    break
                
                page_products = result['products']
                if not page_products:
                    break
                
                # Processa produtos da página
                for product_data in page_products:
                    try:
                        product = self._parse_shopify_product(product_data, store)
                        if product:
                            products.append(product)
                            collected += 1
                            
                            if collected >= limit:
                                break
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao parsear produto Shopify: {e}")
                        continue
                
                # Verifica se há mais páginas
                link_header = None  # Shopify retorna no header Link
                if 'link' in getattr(result, 'headers', {}):
                    link_header = result.headers.get('link')
                
                if link_header and 'rel="next"' in link_header:
                    # Extrai page_info do header Link
                    import re
                    match = re.search(r'page_info=([^&>]+)', link_header)
                    page_info = match.group(1) if match else None
                else:
                    break
            
            return products
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar produtos da loja {store['name']}: {e}")
            return []
    
    def get_product_details(self, store: Dict, product_id: str) -> Optional[Dict]:
        """Obtém detalhes completos de um produto específico"""
        try:
            result = self._make_request(store, f'/products/{product_id}.json')
            
            if not result or 'product' not in result:
                return None
            
            product = self._parse_shopify_product(result['product'], store, detailed=True)
            
            if product:
                logger.debug(f"✅ Shopify Product Details: {product_id}")
            
            return product
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter detalhes Shopify {product_id}: {e}")
            return None
    
    def _parse_shopify_product(self, product_data: Dict, store: Dict, detailed: bool = False) -> Optional[Dict]:
        """Converte produto Shopify para formato padrão"""
        try:
            # Pega primeira variante (ou principal)
            variants = product_data.get('variants', [])
            main_variant = variants[0] if variants else {}
            
            # Preços
            price = float(main_variant.get('price', 0))
            compare_price = main_variant.get('compare_at_price')
            promotional_price = price if compare_price and float(compare_price) > price else None
            
            # Imagens
            images = product_data.get('images', [])
            main_image = images[0].get('src', '') if images else ''
            additional_images = [img.get('src', '') for img in images[1:]] if len(images) > 1 else []
            
            # Handle do produto (slug)
            handle = product_data.get('handle', '')
            product_url = f"https://{store['domain']}/products/{handle}" if handle else ''
            
            # Tags como categorias
            tags = product_data.get('tags', '')
            categories = [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else []
            main_category = categories[0] if categories else ''
            
            # Status
            published = product_data.get('published_at') is not None
            available = any(v.get('available', False) for v in variants)
            
            # Estoque total
            total_inventory = sum(v.get('inventory_quantity', 0) for v in variants if v.get('inventory_quantity'))
            
            product = {
                # Identificação
                'product_id': str(product_data['id']),
                'source': 'shopify',
                'source_url': product_url,
                'loja': store['name'],
                'shopify_store': store['domain'],
                
                # Informações básicas
                'produto': product_data.get('title', ''),
                'descricao': product_data.get('body_html', '').replace('<[^>]*>', '') if detailed else '',
                'preco': price,
                'preco_promocional': float(promotional_price) if promotional_price else None,
                'moeda': 'BRL',  # Assumindo BRL, pode ser configurável
                
                # Categorização
                'categoria': main_category,
                'tags': categories,
                'product_type': product_data.get('product_type', ''),
                'vendor': product_data.get('vendor', ''),
                
                # Disponibilidade
                'disponibilidade': 'Disponível' if (published and available) else 'Indisponível',
                'publicado': published,
                'estoque': total_inventory,
                
                # Variações
                'total_variacoes': len(variants),
                'opcoes_variacao': [opt.get('name') for opt in product_data.get('options', [])],
                
                # Imagens
                'imagem_original': main_image,
                'imagens_adicionais': additional_images,
                
                # SEO
                'seo_title': product_data.get('seo_title', ''),
                'seo_description': product_data.get('seo_description', ''),
                
                # Metadados
                'scraped_at': datetime.now().isoformat(),
                'api_source': 'shopify_admin',
                
                # Dados específicos Shopify
                'shopify_handle': handle,
                'shopify_created_at': product_data.get('created_at'),
                'shopify_updated_at': product_data.get('updated_at'),
                'shopify_published_at': product_data.get('published_at'),
                'shopify_template_suffix': product_data.get('template_suffix'),
            }
            
            # Adiciona informações detalhadas das variantes se solicitado
            if detailed and variants:
                variant_details = []
                for variant in variants:
                    variant_info = {
                        'id': variant.get('id'),
                        'title': variant.get('title'),
                        'price': float(variant.get('price', 0)),
                        'compare_price': variant.get('compare_at_price'),
                        'sku': variant.get('sku'),
                        'barcode': variant.get('barcode'),
                        'inventory_quantity': variant.get('inventory_quantity', 0),
                        'weight': variant.get('weight'),
                        'option1': variant.get('option1'),
                        'option2': variant.get('option2'),
                        'option3': variant.get('option3'),
                        'available': variant.get('available', False)
                    }
                    variant_details.append(variant_info)
                
                product['variants_details'] = variant_details
            
            return product
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parsear produto Shopify: {e}")
            return None
    
    def get_store_info(self, store: Dict) -> Optional[Dict]:
        """Obtém informações da loja"""
        try:
            result = self._make_request(store, '/shop.json')
            
            if not result or 'shop' not in result:
                return None
            
            shop_data = result['shop']
            
            return {
                'name': shop_data.get('name'),
                'domain': shop_data.get('domain'),
                'email': shop_data.get('email'),
                'currency': shop_data.get('currency'),
                'timezone': shop_data.get('iana_timezone'),
                'plan_name': shop_data.get('plan_name'),
                'country': shop_data.get('country_name'),
                'created_at': shop_data.get('created_at'),
                'updated_at': shop_data.get('updated_at')
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter info da loja {store['name']}: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Testa conectividade com todas as lojas"""
        try:
            logger.info("🧪 Testando conexões Shopify...")
            
            connected_stores = 0
            
            for store in self.stores:
                if not store['domain'] or not store['admin_token']:
                    logger.warning(f"⚠️ {store['name']}: configuração incompleta")
                    continue
                
                logger.info(f"🔍 Testando {store['name']} ({store['domain']})...")
                
                # Testa com informações da loja
                shop_info = self.get_store_info(store)
                
                if shop_info:
                    logger.success(f"✅ {store['name']}: {shop_info['name']} ({shop_info['currency']})")
                    connected_stores += 1
                else:
                    logger.error(f"❌ {store['name']}: falha na conexão")
            
            success = connected_stores > 0
            
            if success:
                logger.success(f"✅ Shopify: {connected_stores} loja(s) conectada(s)!")
            else:
                logger.error("❌ Nenhuma loja Shopify conectada")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Erro no teste Shopify: {e}")
            return False


if __name__ == "__main__":
    # Teste da classe
    shopify = ShopifyConnector()
    
    if shopify.test_connection():
        # Teste de coleta de produtos
        products = shopify.get_all_products(limit_per_store=5)
        logger.info(f"✅ Teste de produtos: {len(products)} produtos coletados")
        
        # Mostra alguns resultados
        for i, product in enumerate(products[:3]):
            logger.info(f"  {i+1}. {product['produto'][:50]}... - R$ {product['preco']:.2f} ({product['loja']})")
    else:
        logger.error("❌ Falha nos testes de conectividade")