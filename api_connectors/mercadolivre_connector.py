#!/usr/bin/env python3
"""
Mercado Livre API Connector
Integração com MercadoLibre API para coleta de produtos
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


class MercadoLivreConnector:
    """Conector para MercadoLibre API"""
    
    def __init__(self):
        self.app_id = os.getenv('MERCADOLIVRE_APP_ID')
        self.client_secret = os.getenv('MERCADOLIVRE_CLIENT_SECRET')
        self.access_token = os.getenv('MERCADOLIVRE_ACCESS_TOKEN')
        self.refresh_token = os.getenv('MERCADOLIVRE_REFRESH_TOKEN')
        self.user_id = os.getenv('MERCADOLIVRE_USER_ID')
        
        self.base_url = "https://api.mercadolibre.com"
        self.session = requests.Session()
        self.rate_limit_delay = 1.0  # 1 segundo entre requests
        
        # Headers padrão
        self._update_auth_headers()
        
        logger.info("🛒 MercadoLibre Connector inicializado")
    
    def _update_auth_headers(self):
        """Atualiza headers de autorização"""
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def refresh_access_token(self) -> bool:
        """Renova o token de acesso usando refresh token"""
        try:
            logger.info("🔄 Renovando token MercadoLibre...")
            
            auth_url = "https://api.mercadolibre.com/oauth/token"
            
            data = {
                'grant_type': 'refresh_token',
                'client_id': self.app_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token
            }
            
            response = requests.post(auth_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token', self.refresh_token)
                
                self._update_auth_headers()
                
                logger.success("✅ Token MercadoLibre renovado com sucesso")
                return True
            else:
                logger.error(f"❌ Erro ao renovar token ML: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro na renovação do token ML: {e}")
            return False
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Faz requisição com rate limiting e tratamento de erros"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            logger.debug(f"📞 ML API Request: {url}")
            
            response = self.session.get(url, params=params)
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.warning("⚠️ Token expirado - tentando renovar...")
                if self.refresh_access_token():
                    logger.info("🔄 Tentando novamente com token renovado...")
                    return self._make_request(endpoint, params)
                else:
                    logger.error("❌ Falha ao renovar token ML")
                    return None
            elif response.status_code == 429:
                logger.warning("⚠️ Rate limit atingido - aguardando...")
                time.sleep(5)
                return self._make_request(endpoint, params)
            else:
                logger.error(f"❌ ML API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na requisição ML: {e}")
            return None
    
    def search_products(self, query: str, limit: int = 50, category: Optional[str] = None) -> List[Dict]:
        """Busca produtos no MercadoLibre"""
        try:
            params = {
                'q': query,
                'limit': min(limit, 50),  # ML limita a 50 por página
                'condition': 'new',
                'sort': 'relevance',
                'buying_mode': 'buy_it_now'
            }
            
            if category:
                params['category'] = category
            
            results = self._make_request('/sites/MLB/search', params)
            
            if not results:
                return []
            
            products = []
            
            for item in results.get('results', []):
                try:
                    product = self._parse_search_item(item)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao parsear item ML: {e}")
                    continue
            
            logger.info(f"✅ ML Search: {len(products)} produtos encontrados para '{query}'")
            return products
            
        except Exception as e:
            logger.error(f"❌ Erro na busca ML: {e}")
            return []
    
    def get_product_details(self, product_id: str) -> Optional[Dict]:
        """Obtém detalhes completos de um produto"""
        try:
            # Dados básicos do produto
            product_data = self._make_request(f'/items/{product_id}')
            if not product_data:
                return None
            
            # Descrição do produto
            description_data = self._make_request(f'/items/{product_id}/description')
            
            # Combina dados
            detailed_product = self._parse_detailed_item(product_data, description_data)
            
            if detailed_product:
                logger.debug(f"✅ ML Product Details: {product_id}")
            
            return detailed_product
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter detalhes ML {product_id}: {e}")
            return None
    
    def get_categories(self) -> List[Dict]:
        """Lista categorias disponíveis no ML Brasil"""
        try:
            categories_data = self._make_request('/sites/MLB/categories')
            
            if not categories_data:
                return []
            
            categories = []
            for cat in categories_data:
                categories.append({
                    'id': cat['id'],
                    'name': cat['name'],
                    'source': 'mercadolivre'
                })
            
            logger.info(f"✅ ML Categories: {len(categories)} categorias carregadas")
            return categories
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar categorias ML: {e}")
            return []
    
    def _parse_search_item(self, item: Dict) -> Optional[Dict]:
        """Converte item da busca para formato padrão"""
        try:
            # Preço principal
            price = item.get('price', 0)
            
            # Preço promocional se disponível
            original_price = item.get('original_price')
            promotional_price = price if original_price and original_price > price else None
            
            # Imagens
            thumbnail = item.get('thumbnail', '').replace('-I.jpg', '-O.jpg')  # Imagem maior
            
            product = {
                # Identificação
                'product_id': item['id'],
                'source': 'mercadolivre',
                'source_url': item.get('permalink', ''),
                
                # Informações básicas
                'produto': item['title'],
                'descricao': '',  # Não vem na busca
                'preco': float(price),
                'preco_promocional': float(promotional_price) if promotional_price else None,
                'moeda': item.get('currency_id', 'BRL'),
                
                # Categorização
                'categoria': item.get('category_id', ''),
                'categoria_nome': '',  # Precisaria de outra chamada
                
                # Disponibilidade
                'disponibilidade': 'Disponível' if item.get('available_quantity', 0) > 0 else 'Esgotado',
                'estoque': item.get('available_quantity', 0),
                
                # Qualidade/Condição
                'condicao': item.get('condition', 'new'),
                'reputacao_vendedor': item.get('seller', {}).get('seller_reputation', {}).get('power_seller_status'),
                
                # Localização
                'estado': item.get('address', {}).get('state_name', ''),
                'cidade': item.get('address', {}).get('city_name', ''),
                
                # Imagens
                'imagem_original': thumbnail,
                'imagens_adicionais': [],
                
                # Metadados
                'scraped_at': datetime.now().isoformat(),
                'api_source': 'mercadolivre_search',
                
                # Dados específicos ML
                'ml_listing_type': item.get('listing_type_id'),
                'ml_free_shipping': item.get('shipping', {}).get('free_shipping', False),
                'ml_seller_id': item.get('seller', {}).get('id'),
            }
            
            return product
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parsear item ML: {e}")
            return None
    
    def _parse_detailed_item(self, product_data: Dict, description_data: Optional[Dict]) -> Optional[Dict]:
        """Converte dados detalhados para formato padrão"""
        try:
            # Preço
            price = product_data.get('price', 0)
            original_price = product_data.get('original_price')
            promotional_price = price if original_price and original_price > price else None
            
            # Imagens (todas as disponíveis)
            images = []
            for picture in product_data.get('pictures', []):
                img_url = picture.get('secure_url', picture.get('url', ''))
                if img_url:
                    images.append(img_url)
            
            # Atributos/Variações
            attributes = {}
            for attr in product_data.get('attributes', []):
                attr_name = attr.get('name', attr.get('id', ''))
                attr_value = attr.get('value_name', str(attr.get('value', '')))
                if attr_name and attr_value:
                    attributes[attr_name] = attr_value
            
            # Descrição
            description = ""
            if description_data:
                description = description_data.get('plain_text', '')
            
            product = {
                # Identificação
                'product_id': product_data['id'],
                'source': 'mercadolivre',
                'source_url': product_data.get('permalink', ''),
                
                # Informações básicas
                'produto': product_data['title'],
                'descricao': description,
                'preco': float(price),
                'preco_promocional': float(promotional_price) if promotional_price else None,
                'moeda': product_data.get('currency_id', 'BRL'),
                
                # Categorização
                'categoria': product_data.get('category_id', ''),
                
                # Disponibilidade
                'disponibilidade': 'Disponível' if product_data.get('available_quantity', 0) > 0 else 'Esgotado',
                'estoque': product_data.get('available_quantity', 0),
                
                # Qualidade
                'condicao': product_data.get('condition', 'new'),
                
                # Imagens
                'imagem_original': images[0] if images else '',
                'imagens_adicionais': images[1:] if len(images) > 1 else [],
                
                # Atributos
                'atributos': attributes,
                
                # Metadados
                'scraped_at': datetime.now().isoformat(),
                'api_source': 'mercadolivre_details',
                
                # Dados específicos ML
                'ml_listing_type': product_data.get('listing_type_id'),
                'ml_free_shipping': product_data.get('shipping', {}).get('free_shipping', False),
                'ml_warranty': product_data.get('warranty'),
                'ml_video_id': product_data.get('video_id'),
            }
            
            return product
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parsear detalhes ML: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Testa conectividade com a API"""
        try:
            logger.info("🧪 Testando conexão MercadoLibre API...")
            
            # Teste simples de busca
            result = self._make_request('/sites/MLB/search', {'q': 'smartphone', 'limit': 1})
            
            if result and 'results' in result:
                total = result.get('paging', {}).get('total', 0)
                logger.success(f"✅ ML API conectada! {total:,} produtos disponíveis")
                return True
            else:
                logger.error("❌ ML API não respondeu corretamente")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no teste ML API: {e}")
            return False


if __name__ == "__main__":
    # Teste da classe
    ml = MercadoLivreConnector()
    
    if ml.test_connection():
        # Teste de busca
        products = ml.search_products("smartphone samsung", limit=5)
        logger.info(f"Encontrados {len(products)} produtos")
        
        # Teste de detalhes
        if products:
            details = ml.get_product_details(products[0]['product_id'])
            if details:
                logger.info(f"Detalhes obtidos para: {details['produto']}")