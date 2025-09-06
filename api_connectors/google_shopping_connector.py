#!/usr/bin/env python3
"""
Google Shopping API Connector
Integração com Google Custom Search API + SerpAPI para coleta de produtos
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


class GoogleShoppingConnector:
    """Conector para Google Shopping via Custom Search e SerpAPI"""
    
    def __init__(self):
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.serpapi_key = os.getenv('SERPAPI_KEY')
        
        # Google CSE IDs para diferentes tipos de busca
        self.cse_ids = os.getenv('GOOGLE_CSE_IDS', '').split(',')
        
        self.session = requests.Session()
        self.rate_limit_delay = 1.0
        
        logger.info("🔍 Google Shopping Connector inicializado")
        logger.info(f"📡 CSE Engines: {len(self.cse_ids)} configurados")
    
    def _make_google_request(self, params: Dict) -> Optional[Dict]:
        """Requisição para Google Custom Search API"""
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params['key'] = self.google_api_key
            
            logger.debug(f"📞 Google CSE Request: {params.get('q', '')}")
            
            response = self.session.get(url, params=params)
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"⚠️ Google CSE Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na requisição Google: {e}")
            return None
    
    def _make_serpapi_request(self, params: Dict) -> Optional[Dict]:
        """Requisição para SerpAPI (Google Shopping)"""
        try:
            url = "https://serpapi.com/search"
            params['api_key'] = self.serpapi_key
            params['engine'] = 'google_shopping'
            
            logger.debug(f"📞 SerpAPI Request: {params.get('q', '')}")
            
            response = self.session.get(url, params=params)
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"⚠️ SerpAPI Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na requisição SerpAPI: {e}")
            return None
    
    def search_products_serpapi(self, query: str, limit: int = 20) -> List[Dict]:
        """Busca produtos via SerpAPI Google Shopping"""
        try:
            params = {
                'q': query,
                'num': min(limit, 100),
                'hl': 'pt-br',
                'gl': 'br',
                'location': 'Brazil'
            }
            
            results = self._make_serpapi_request(params)
            
            if not results or 'shopping_results' not in results:
                logger.warning(f"⚠️ SerpAPI: Nenhum resultado para '{query}'")
                return []
            
            products = []
            for item in results['shopping_results']:
                try:
                    product = self._parse_serpapi_item(item, query)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao parsear item SerpAPI: {e}")
                    continue
            
            logger.info(f"✅ SerpAPI: {len(products)} produtos encontrados para '{query}'")
            return products
            
        except Exception as e:
            logger.error(f"❌ Erro na busca SerpAPI: {e}")
            return []
    
    def search_products_cse(self, query: str, limit: int = 20) -> List[Dict]:
        """Busca produtos via Google Custom Search"""
        try:
            all_products = []
            
            # Usa diferentes CSE IDs para obter mais resultados
            for i, cse_id in enumerate(self.cse_ids[:3]):  # Limita a 3 para não explodir
                if not cse_id.strip():
                    continue
                
                params = {
                    'cx': cse_id.strip(),
                    'q': f"{query} preço comprar",
                    'num': min(limit // len(self.cse_ids[:3]) + 1, 10),
                    'searchType': 'image' if i % 2 == 0 else None,
                    'lr': 'lang_pt'
                }
                
                # Remove searchType se None
                if params['searchType'] is None:
                    del params['searchType']
                
                results = self._make_google_request(params)
                
                if results and 'items' in results:
                    for item in results['items']:
                        try:
                            product = self._parse_cse_item(item, query)
                            if product:
                                all_products.append(product)
                        except Exception as e:
                            logger.debug(f"⚠️ Erro ao parsear item CSE: {e}")
                            continue
                
                # Pausa entre CSEs
                time.sleep(0.5)
            
            # Remove duplicatas por URL
            seen_urls = set()
            unique_products = []
            for product in all_products:
                url = product.get('source_url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_products.append(product)
            
            logger.info(f"✅ Google CSE: {len(unique_products)} produtos únicos para '{query}'")
            return unique_products[:limit]
            
        except Exception as e:
            logger.error(f"❌ Erro na busca CSE: {e}")
            return []
    
    def search_products(self, query: str, limit: int = 50, method: str = 'both') -> List[Dict]:
        """Busca produtos usando SerpAPI e/ou CSE"""
        try:
            all_products = []
            
            if method in ['serpapi', 'both']:
                serpapi_products = self.search_products_serpapi(query, limit // 2 if method == 'both' else limit)
                all_products.extend(serpapi_products)
            
            if method in ['cse', 'both']:
                cse_products = self.search_products_cse(query, limit // 2 if method == 'both' else limit)
                all_products.extend(cse_products)
            
            # Remove duplicatas finais
            seen_products = set()
            unique_products = []
            for product in all_products:
                key = (product.get('produto', ''), product.get('preco', 0))
                if key not in seen_products:
                    seen_products.add(key)
                    unique_products.append(product)
            
            logger.info(f"✅ Google Search Total: {len(unique_products)} produtos para '{query}'")
            return unique_products[:limit]
            
        except Exception as e:
            logger.error(f"❌ Erro na busca Google: {e}")
            return []
    
    def _parse_serpapi_item(self, item: Dict, query: str) -> Optional[Dict]:
        """Converte item SerpAPI para formato padrão"""
        try:
            # Preço
            price_str = item.get('price', item.get('extracted_price', '0'))
            price = self._extract_price(price_str)
            
            # Informações básicas
            title = item.get('title', '')
            link = item.get('link', '')
            thumbnail = item.get('thumbnail', '')
            
            # Fonte/Loja
            source = item.get('source', '')
            if not source and link:
                # Extrai domínio da URL
                from urllib.parse import urlparse
                source = urlparse(link).netloc
            
            product = {
                # Identificação
                'product_id': f"google_serp_{abs(hash(link))}",
                'source': 'google_shopping',
                'source_url': link,
                'loja': source,
                
                # Informações básicas
                'produto': title,
                'descricao': item.get('snippet', ''),
                'preco': price,
                'preco_promocional': None,
                'moeda': 'BRL',
                
                # Categorização
                'categoria': '',
                'query_busca': query,
                
                # Disponibilidade
                'disponibilidade': 'Disponível',
                
                # Imagens
                'imagem_original': thumbnail,
                'imagens_adicionais': [],
                
                # Qualidade/Rating
                'rating': item.get('rating'),
                'reviews': item.get('reviews'),
                
                # Metadados
                'scraped_at': datetime.now().isoformat(),
                'api_source': 'serpapi_shopping',
                
                # Dados específicos
                'serpapi_position': item.get('position'),
                'serpapi_product_id': item.get('product_id'),
            }
            
            return product
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parsear SerpAPI: {e}")
            return None
    
    def _parse_cse_item(self, item: Dict, query: str) -> Optional[Dict]:
        """Converte item Google CSE para formato padrão"""
        try:
            title = item.get('title', '')
            link = item.get('link', '')
            snippet = item.get('snippet', '')
            
            # Tenta extrair preço do snippet
            price = self._extract_price(snippet)
            
            # Imagem
            thumbnail = ''
            if 'pagemap' in item and 'cse_thumbnail' in item['pagemap']:
                thumbnail = item['pagemap']['cse_thumbnail'][0].get('src', '')
            
            # Fonte/Domínio
            from urllib.parse import urlparse
            domain = urlparse(link).netloc
            
            product = {
                # Identificação
                'product_id': f"google_cse_{abs(hash(link))}",
                'source': 'google_search',
                'source_url': link,
                'loja': domain,
                
                # Informações básicas
                'produto': title,
                'descricao': snippet,
                'preco': price,
                'preco_promocional': None,
                'moeda': 'BRL',
                
                # Categorização
                'categoria': '',
                'query_busca': query,
                
                # Disponibilidade
                'disponibilidade': 'Disponível',
                
                # Imagens
                'imagem_original': thumbnail,
                'imagens_adicionais': [],
                
                # Metadados
                'scraped_at': datetime.now().isoformat(),
                'api_source': 'google_cse',
                
                # Dados específicos
                'cse_display_link': item.get('displayLink'),
                'cse_formatted_url': item.get('formattedUrl'),
            }
            
            return product
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parsear CSE: {e}")
            return None
    
    def _extract_price(self, text: str) -> float:
        """Extrai preço de texto"""
        try:
            import re
            
            if not text:
                return 0.0
            
            # Padrões de preço em português
            patterns = [
                r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # R$ 1.234,56
                r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?) *reais?',  # 1.234,56 reais
                r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # 1.234,56
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    price_str = match.group(1)
                    # Converte formato brasileiro para float
                    price_str = price_str.replace('.', '').replace(',', '.')
                    return float(price_str)
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def test_connection(self) -> bool:
        """Testa conectividade com APIs"""
        try:
            logger.info("🧪 Testando APIs Google...")
            
            # Teste SerpAPI
            serpapi_ok = False
            if self.serpapi_key:
                test_serp = self.search_products_serpapi("smartphone", 2)
                serpapi_ok = len(test_serp) > 0
                logger.info(f"📡 SerpAPI: {'✅' if serpapi_ok else '❌'}")
            
            # Teste Google CSE
            cse_ok = False
            if self.google_api_key and self.cse_ids:
                test_cse = self.search_products_cse("smartphone", 2)
                cse_ok = len(test_cse) > 0
                logger.info(f"🔍 Google CSE: {'✅' if cse_ok else '❌'}")
            
            success = serpapi_ok or cse_ok
            
            if success:
                logger.success("✅ Google APIs conectadas!")
            else:
                logger.error("❌ Nenhuma API Google funcionando")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Erro no teste Google APIs: {e}")
            return False


if __name__ == "__main__":
    # Teste da classe
    google = GoogleShoppingConnector()
    
    if google.test_connection():
        # Teste de busca completo
        products = google.search_products("smartphone samsung", limit=10, method='both')
        logger.info(f"✅ Teste completo: {len(products)} produtos encontrados")
        
        # Mostra alguns resultados
        for i, product in enumerate(products[:3]):
            logger.info(f"  {i+1}. {product['produto'][:50]}... - R$ {product['preco']:.2f}")
    else:
        logger.error("❌ Falha nos testes de conectividade")