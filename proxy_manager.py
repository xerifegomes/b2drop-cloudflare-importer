#!/usr/bin/env python3
"""
Proxy Manager - Sistema de proxies rotativos para scraping
Gerencia proxies para evitar rate limits e bloqueios
"""

import os
import random
import requests
import time
from typing import Dict, List, Optional, Tuple
from loguru import logger
from datetime import datetime, timedelta


class ProxyManager:
    """Gerenciador de proxies rotativos"""
    
    def __init__(self):
        # Proxies públicos gratuitos (para teste)
        self.free_proxies = [
            "http://51.79.50.22:9300",
            "http://51.79.50.46:9300", 
            "http://172.105.107.25:9999",
            "http://139.99.88.244:8080",
            "http://43.134.68.153:3128",
        ]
        
        # Proxies premium (será configurado quando necessário)
        self.premium_proxies = []
        
        # Status dos proxies
        self.proxy_status = {}
        self.current_proxy_index = 0
        self.failed_proxies = set()
        
        # Configurações
        self.max_retries_per_proxy = 3
        self.proxy_timeout = 10
        self.rotation_interval = 100  # Troca proxy a cada N requests
        self.request_count = 0
        
        logger.info("🌐 Proxy Manager inicializado")
        logger.info(f"🔄 Proxies disponíveis: {len(self.free_proxies)}")
    
    def get_working_proxy(self) -> Optional[str]:
        """Retorna um proxy funcionando"""
        try:
            available_proxies = [p for p in self.free_proxies if p not in self.failed_proxies]
            
            if not available_proxies:
                logger.warning("⚠️ Todos os proxies falharam, resetando lista")
                self.failed_proxies.clear()
                available_proxies = self.free_proxies.copy()
            
            if not available_proxies:
                logger.error("❌ Nenhum proxy disponível")
                return None
            
            # Rotação baseada em contador de requests
            if self.request_count % self.rotation_interval == 0:
                self.current_proxy_index = (self.current_proxy_index + 1) % len(available_proxies)
                logger.debug(f"🔄 Rotação de proxy: {self.current_proxy_index}")
            
            proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
            self.request_count += 1
            
            return proxy
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter proxy: {e}")
            return None
    
    def test_proxy(self, proxy: str, test_url: str = "https://httpbin.org/ip") -> bool:
        """Testa se um proxy está funcionando"""
        try:
            proxies = {"http": proxy, "https": proxy}
            
            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=self.proxy_timeout
            )
            
            if response.status_code == 200:
                logger.debug(f"✅ Proxy OK: {proxy}")
                return True
            else:
                logger.warning(f"⚠️ Proxy retornou {response.status_code}: {proxy}")
                return False
                
        except Exception as e:
            logger.debug(f"❌ Proxy falhou: {proxy} - {e}")
            return False
    
    def validate_all_proxies(self) -> List[str]:
        """Valida todos os proxies disponíveis"""
        try:
            logger.info("🧪 Validando proxies...")
            
            working_proxies = []
            
            for proxy in self.free_proxies:
                if self.test_proxy(proxy):
                    working_proxies.append(proxy)
                    self.proxy_status[proxy] = {
                        "status": "working",
                        "last_tested": datetime.now(),
                        "success_count": 0,
                        "fail_count": 0
                    }
                else:
                    self.failed_proxies.add(proxy)
                    self.proxy_status[proxy] = {
                        "status": "failed",
                        "last_tested": datetime.now(),
                        "success_count": 0,
                        "fail_count": 1
                    }
                
                time.sleep(1)  # Rate limit para testes
            
            logger.info(f"✅ Proxies validados: {len(working_proxies)}/{len(self.free_proxies)}")
            return working_proxies
            
        except Exception as e:
            logger.error(f"❌ Erro na validação de proxies: {e}")
            return []
    
    def make_request_with_proxy(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Faz requisição usando proxy rotativo"""
        try:
            max_attempts = min(3, len(self.free_proxies))
            
            for attempt in range(max_attempts):
                proxy = self.get_working_proxy()
                
                if not proxy:
                    logger.warning("⚠️ Nenhum proxy disponível, usando requisição direta")
                    return requests.get(url, **kwargs)
                
                try:
                    proxies = {"http": proxy, "https": proxy}
                    kwargs_with_proxy = kwargs.copy()
                    kwargs_with_proxy["proxies"] = proxies
                    kwargs_with_proxy["timeout"] = self.proxy_timeout
                    
                    logger.debug(f"📞 Request via proxy: {proxy}")
                    response = requests.get(url, **kwargs_with_proxy)
                    
                    # Sucesso - atualiza estatísticas
                    if proxy in self.proxy_status:
                        self.proxy_status[proxy]["success_count"] += 1
                    
                    return response
                    
                except Exception as e:
                    logger.warning(f"⚠️ Falha no proxy {proxy}: {e}")
                    
                    # Marca proxy como falho temporariamente
                    self.failed_proxies.add(proxy)
                    if proxy in self.proxy_status:
                        self.proxy_status[proxy]["fail_count"] += 1
                    
                    continue
            
            # Se todos os proxies falharam, tenta sem proxy
            logger.warning("⚠️ Todos os proxies falharam, tentando sem proxy")
            return requests.get(url, **kwargs)
            
        except Exception as e:
            logger.error(f"❌ Erro na requisição com proxy: {e}")
            return None
    
    def get_proxy_stats(self) -> Dict:
        """Retorna estatísticas dos proxies"""
        try:
            total_proxies = len(self.free_proxies)
            working_proxies = len([p for p in self.free_proxies if p not in self.failed_proxies])
            failed_proxies = len(self.failed_proxies)
            
            stats = {
                "total_proxies": total_proxies,
                "working_proxies": working_proxies,
                "failed_proxies": failed_proxies,
                "success_rate": (working_proxies / total_proxies * 100) if total_proxies > 0 else 0,
                "current_proxy_index": self.current_proxy_index,
                "total_requests": self.request_count,
                "proxy_details": self.proxy_status
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro nas estatísticas: {e}")
            return {}
    
    def reset_failed_proxies(self):
        """Reseta lista de proxies com falha"""
        self.failed_proxies.clear()
        logger.info("🔄 Lista de proxies falhados resetada")
    
    def add_premium_proxies(self, proxy_list: List[str]):
        """Adiciona proxies premium à lista"""
        self.premium_proxies.extend(proxy_list)
        # Prioriza proxies premium
        self.free_proxies = self.premium_proxies + self.free_proxies
        logger.info(f"🌟 {len(proxy_list)} proxies premium adicionados")


# Integração com Google Shopping Connector
class ProxyEnabledGoogleConnector:
    """Google Shopping Connector com suporte a proxies"""
    
    def __init__(self):
        from api_connectors.google_shopping_connector import GoogleShoppingConnector
        
        self.base_connector = GoogleShoppingConnector()
        self.proxy_manager = ProxyManager()
        
        # Valida proxies na inicialização
        self.proxy_manager.validate_all_proxies()
        
        logger.info("🌐 Google Connector com proxies inicializado")
    
    def search_products_with_proxy(self, query: str, limit: int = 50) -> List[Dict]:
        """Busca produtos usando proxies rotativos"""
        try:
            logger.info(f"🔍 Buscando '{query}' com rotação de proxies...")
            
            # Usa o método original mas com requisições via proxy
            original_make_request = self.base_connector._make_serpapi_request
            
            def proxied_request(params):
                url = "https://serpapi.com/search"
                params['api_key'] = self.base_connector.serpapi_key
                params['engine'] = 'google_shopping'
                
                response = self.proxy_manager.make_request_with_proxy(url, params=params)
                
                if response and response.status_code == 200:
                    return response.json()
                else:
                    return None
            
            # Substitui método temporariamente
            self.base_connector._make_serpapi_request = proxied_request
            
            # Executa busca
            results = self.base_connector.search_products_serpapi(query, limit)
            
            # Restaura método original
            self.base_connector._make_serpapi_request = original_make_request
            
            logger.info(f"✅ Busca com proxy concluída: {len(results)} resultados")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro na busca com proxy: {e}")
            return []


if __name__ == "__main__":
    # Teste do sistema de proxies
    proxy_mgr = ProxyManager()
    
    # Valida proxies
    working = proxy_mgr.validate_all_proxies()
    print(f"✅ Proxies funcionando: {len(working)}")
    
    # Teste de requisição
    if working:
        response = proxy_mgr.make_request_with_proxy("https://httpbin.org/ip")
        if response:
            print(f"✅ Requisição via proxy bem-sucedida: {response.json()}")
        
        # Estatísticas
        stats = proxy_mgr.get_proxy_stats()
        print(f"📊 Taxa de sucesso: {stats['success_rate']:.1f}%")
    
    # Teste com Google Shopping
    print("\n🧪 Testando Google Shopping com proxies...")
    google_proxy = ProxyEnabledGoogleConnector()
    products = google_proxy.search_products_with_proxy("smartphone", 5)
    print(f"✅ Produtos encontrados: {len(products)}")