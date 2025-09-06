#!/usr/bin/env python3
"""
Top Products Aggregator - Produtos Físicos Mais Vendidos (120 dias)
Agrega dados de múltiplas APIs focando em produtos físicos top de vendas
"""
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
import pandas as pd

from api_connectors.google_shopping_connector import GoogleShoppingConnector
from api_connectors.shopify_connector import ShopifyConnector
from cloudflare_storage_fixed import CloudflareStorage

# Carrega variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv('.env.apis')
except ImportError:
    logger.warning("⚠️  python-dotenv não encontrado, usando variáveis de ambiente do sistema")

class TopProductsAggregator:
    """Agregador inteligente de produtos físicos mais vendidos"""
    
    def __init__(self):
        # Inicializa apenas conectores públicos (sem lojas específicas)
        self.google_connector = GoogleShoppingConnector()
        
        # Storage Cloudflare (igual à 1ª fase)
        self.storage = CloudflareStorage()
        
        # Conectores de loja (desabilitados por enquanto)
        self.shopify_connector = None  # Será habilitado quando conectar lojas
        self.mercadolivre_connector = None  # Será habilitado quando necessário
        
        # Configurações de busca
        self.search_period_days = 120
        self.min_score_threshold = 7.0  # Pontuação mínima para considerar "top"
        
        # Categorias físicas para busca (exemplo)
        self.top_physical_categories = [
            "eletrônicos", "celulares", "fones de ouvido", "smartwatches",
            "eletrodomésticos", "geladeiras", "fogões", "máquinas de lavar",
            "moda", "roupas", "calçados", "acessórios",
            "casa e decoração", "móveis", "iluminação", "utensílios de cozinha",
            "saúde e beleza", "cosméticos", "perfumes", "suplementos",
            "esportes e lazer", "bicicletas", "equipamentos de ginástica",
            "brinquedos", "jogos", "videogames",
            "ferramentas", "jardinagem", "material de construção",
            "automotivo", "pneus", "peças",
            "livros", "papelaria",
            "pet shop", "ração", "acessórios para pets",
            "bebês", "fraldas", "carrinhos",
            "alimentos e bebidas", "café", "chocolates",
            "joias", "relógios",
            "instrumentos musicais",
            "material de escritório",
            "viagem", "malas", "mochilas",
            "segurança", "câmeras", "alarmes"
        ]
        
        logger.info("🏆 Top Products Aggregator inicializado")
        logger.info(f"📅 Período de análise: {self.search_period_days} dias")
        logger.info(f"🎯 Categorias físicas: {len(self.top_physical_categories)}")
        
        # Inicializa storage Cloudflare
        if self.storage and self.storage.init_r2_bucket():
            logger.success("☁️ Cloudflare Storage conectado (KV + R2)")
        else:
            logger.warning("⚠️ Falha na conexão Cloudflare Storage")

    def collect_trending_products(self, limit_per_category: int = 10) -> List[Dict]:
        """Coleta produtos em tendência das principais categorias"""
        all_products = []
        logger.info("📈 Coletando produtos em tendência...")
        
        for category in self.top_physical_categories:
            logger.info(f"🔍 Buscando em categoria: {category}")
            
            # Google Shopping
            google_products = self.google_connector.search_products(category, limit=limit_per_category)
            for p in google_products:
                p['source'] = 'google'
                p['category_searched'] = category
                all_products.append(p)
            
            # Shopify (desabilitado por enquanto)
            # shopify_products = self.shopify_connector.search_products(category, limit=limit_per_category)
            # for p in shopify_products:
            #     p['source'] = 'shopify'
            #     p['category_searched'] = category
            #     all_products.append(p)
            
            time.sleep(1) # Pequeno delay entre categorias
            
        logger.info(f"Total de produtos brutos coletados: {len(all_products)}")
        return all_products

    def collect_shopify_bestsellers(self) -> List[Dict]:
        """Coleta best-sellers das lojas Shopify configuradas"""
        try:
            # Por enquanto desabilitado - será ativado quando conectar lojas
            if not self.shopify_connector:
                logger.info("🛍️ Shopify connector desabilitado (futuras integrações)")
                return []
            
            logger.info("🛍️ Coletando best-sellers Shopify...")
            
            shopify_products = self.shopify_connector.get_all_products(limit_per_store=20)
            
            standardized_products = []
            for p in shopify_products:
                p['source'] = 'shopify'
                standardized_products.append(p) # Padronização será feita no store_products_batch
            
            logger.info(f"Total de best-sellers Shopify coletados: {len(standardized_products)}")
            return standardized_products
        except Exception as e:
            logger.error(f"❌ Erro ao coletar best-sellers Shopify: {e}")
            return []

    def calculate_trending_score(self, product: Dict) -> float:
        """Calcula um score de tendência para o produto (0-10)"""
        score = 0.0
        
        # Baseado em rating (0-5)
        rating = product.get('rating', 0)
        score += rating * 1.0 # Peso 1 para rating
        
        # Baseado em número de reviews (logarítmico)
        reviews = product.get('reviews', 0)
        if reviews > 0:
            score += min(5.0, (reviews**0.3) * 0.5) # Peso 0.5 para reviews, com cap
            
        # Baseado em preço (produtos muito baratos ou muito caros podem ter score menor)
        price = product.get('preco', 0)
        if price > 0:
            if price < 10 or price > 500: # Exemplo: penaliza extremos
                score -= 1.0
            elif price > 50 and price < 200: # Exemplo: favorece faixa comum
                score += 1.0
                
        # Normaliza para 0-10 (exemplo simples)
        return max(0.0, min(10.0, score))

    def remove_duplicates(self, products: List[Dict]) -> List[Dict]:
        """Remove duplicatas baseadas em uma chave única (produto + source)."""
        unique_products = {}
        for p in products:
            # Cria uma chave única combinando nome do produto e fonte
            product_name = p.get('produto', '').lower()
            source = p.get('source', '').lower()
            unique_key = f"{product_name}_{source}"
            
            if unique_key not in unique_products:
                unique_products[unique_key] = p
            else:
                # Se já existe, mantém o que tiver maior trending_score
                existing_score = unique_products[unique_key].get('trending_score', 0)
                current_score = p.get('trending_score', 0)
                if current_score > existing_score:
                    unique_products[unique_key] = p
        
        return list(unique_products.values())

    def standardize_product(self, raw_product: Dict) -> Dict:
        """Padroniza produto para formato unificado Cloudflare com proteção contra colisão"""
        try:
            # Gera ID único SEGURO usando método padronizado
            source = raw_product.get('source', 'unknown')
            produto_nome = raw_product.get('produto', '')
            
            # ✅ CORREÇÃO: Usa método seguro do CloudflareStorage ao invés de hash simples
            if hasattr(self.storage, 'generate_secure_product_id'):
                unified_id = self.storage.generate_secure_product_id(produto_nome, source, raw_product)
            else:
                # Fallback seguro se método não existir
                import hashlib
                hash_input = f"{produto_nome}_{raw_product.get('source_url', '')}_{raw_product.get('preco', 0)}"
                hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
                unified_id = f"{source}_{hash_value}"
            
            # Preços padronizados
            preco = float(raw_product.get('preco', 0))
            preco_promocional = raw_product.get('preco_promocional')
            if preco_promocional:
                preco_promocional = float(preco_promocional)
            
            # Categoria padronizada
            categoria = raw_product.get('categoria', '')
            if not categoria:
                categoria = raw_product.get('category_searched', 'Outros')
            
            # URL da imagem principal
            imagem_original = raw_product.get('imagem_original', '')
            
            # Produto padronizado no formato da 1ª fase
            standardized = {
                # IDs e identificação (SISTEMA PADRONIZADO SEGURO)
                'product_id': unified_id,
                'hash_produto': unified_id,  # Compatibilidade com 1ª fase
                'original_product_id': raw_product.get('product_id', ''),  # ID original da API
                
                # Informações básicas
                'produto': raw_product.get('produto', ''),
                'descricao': raw_product.get('descricao', ''),
                'preco': preco,
                'preco_promocional': preco_promocional,
                'categoria': categoria,
                
                # Disponibilidade
                'disponibilidade': raw_product.get('disponibilidade', 'Disponível'),
                'estoque': raw_product.get('estoque', 0),
                
                # Variações
                'cor': raw_product.get('cor', ''),
                'tamanho': raw_product.get('tamanho', ''),
                'total_variacoes': raw_product.get('total_variacoes', 1), # Será 1 para a maioria dos produtos de API
                
                # Imagens
                'imagem_original': imagem_original,
                'imagens_adicionais': raw_product.get('imagens_adicionais', []), # Lista de URLs
                'imagem_r2': None,  # Será preenchido após upload
                
                # URLs e fonte
                'url_produto': raw_product.get('source_url', ''),
                'loja': raw_product.get('loja', ''),
                'source': source, # Identifica a fonte da API
                
                # Qualidade e reviews
                'rating': raw_product.get('rating'),
                'reviews': raw_product.get('reviews'),
                
                # Trending data (novo)
                'trending_score': raw_product.get('trending_score', 0), # Score calculado
                'category_searched': raw_product.get('category_searched', ''), # Categoria usada na busca
                'query_busca': raw_product.get('query_busca', ''), # Termo de busca
                
                # Metadados
                'scraped_at': raw_product.get('scraped_at', datetime.now().isoformat()),
                'created_at': datetime.now().isoformat(),
                'api_source': raw_product.get('api_source', ''), # Nome da API (ex: Google CSE)
                'data_collection': 'trending_analysis',  # Identifica como 2ª fase
            }
            
            return standardized
            
        except Exception as e:
            logger.error(f"❌ Erro na padronização do produto: {e}")
            return {}

    def store_products_batch(self, products: List[Dict], source: str, upload_images: bool = True) -> Dict:
        """Armazena batch de produtos no Cloudflare (KV + R2) com prefixo de fonte."""
        try:
            if not products:
                return {'success': 0, 'failed': 0, 'images_uploaded': 0}
            
            logger.info(f"💾 Armazenando {len(products)} produtos no Cloudflare da fonte '{source}'...")
            
            success_count = 0
            failed_count = 0
            images_uploaded = 0
            
            for i, raw_product in enumerate(products, 1):
                try:
                    # Padroniza produto
                    standardized_product = self.standardize_product(raw_product)
                    
                    if not standardized_product:
                        failed_count += 1
                        continue
                    
                    # Upload da imagem para R2 (se disponível)
                    if upload_images and standardized_product.get('imagem_original'):
                        r2_url = self.storage.upload_image(
                            standardized_product['imagem_original'],
                            standardized_product['produto']
                        )
                        if r2_url:
                            standardized_product['imagem_r2'] = r2_url
                            images_uploaded += 1
                    
                    # Armazena no KV
                    stored = self.storage.store_product(standardized_product, source) # Passa a fonte aqui
                    
                    if stored: # store_product já retorna True/False
                        success_count += 1
                        if i % 10 == 0:  # Log a cada 10 produtos
                            logger.info(f"📊 Progresso: {i}/{len(products)} produtos processados")
                    else:
                        failed_count += 1
                        logger.warning(f"⚠️ Falha ao armazenar: {standardized_product['produto'][:50]}")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Erro ao processar produto {i}: {e}")
                    continue
            
            result = {
                'success': success_count,
                'failed': failed_count,
                'images_uploaded': images_uploaded,
                'total': len(products)
            }
            
            logger.success(f"✅ Armazenamento concluído: {success_count} sucessos, {failed_count} falhas")
            logger.success(f"🖼️ Imagens uploadadas: {images_uploaded}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro no armazenamento batch: {e}")
            return {'success': 0, 'failed': len(products), 'images_uploaded': 0}

    def generate_trending_report(self, products: List[Dict]) -> Dict:
        """Gera relatório de análise dos produtos trending"""
        try:
            if not products:
                return {}
            
            df = pd.DataFrame(products)
            
            # Calcula score médio
            average_trending_score = df['trending_score'].mean() if 'trending_score' in df else 0
            
            # Top categorias
            top_categories = df['categoria'].value_counts().head(5).to_dict()
            
            # Faixa de preço
            min_price = df['preco'].min() if 'preco' in df else 0
            max_price = df['preco'].max() if 'preco' in df else 0
            
            # Produtos por fonte
            products_by_source = df['source'].value_counts().to_dict()
            
            report = {
                'total_products': len(products),
                'average_trending_score': round(average_trending_score, 2),
                'top_categories': top_categories,
                'min_price': round(min_price, 2),
                'max_price': round(max_price, 2),
                'products_by_source': products_by_source
            }
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Erro na geração do relatório: {e}")
            return {}

    def run_full_analysis(self, save_results: bool = True, store_cloudflare: bool = True) -> Dict:
        """Executa análise completa de produtos trending"""
        try:
            start_time = time.time()
            logger.info("🚀 Iniciando análise completa de produtos trending...")
            
            # Coleta produtos de todas as fontes configuradas
            all_products = self.collect_trending_products()
            
            # Coleta best-sellers Shopify (se habilitado)
            shopify_bestsellers = self.collect_shopify_bestsellers()
            all_products.extend(shopify_bestsellers)
            
            if not all_products:
                logger.warning("Nenhum produto coletado para análise.")
                return {}
            
            # Remove duplicatas (baseado em produto + source)
            unique_products = self.remove_duplicates(all_products)
            
            # Calcula score de tendência para cada produto
            for p in unique_products:
                p['trending_score'] = self.calculate_trending_score(p)
            
            # Ordena por score final
            final_products = sorted(unique_products, key=lambda x: x.get('trending_score', 0), reverse=True)
            
            # Armazena no Cloudflare
            storage_result = {}
            if store_cloudflare and self.storage and final_products:
                logger.info("☁️ Iniciando armazenamento no Cloudflare...")
                storage_result = self.store_products_batch(final_products, source="google_trending", upload_images=True) # Fonte para trending
            
            # Gera relatório
            report = self.generate_trending_report(final_products)
            report['storage_result'] = storage_result  # Adiciona stats de armazenamento
            
            elapsed_time = time.time() - start_time
            
            logger.success(f"✅ Análise concluída em {elapsed_time:.2f} segundos.")
            logger.success(f"🏆 Produtos coletados: {len(final_products)}")
            logger.success(f"📊 Score médio: {report.get('average_trending_score', 0)}")
            
            if storage_result:
                logger.success(f"☁️ Cloudflare: {storage_result['success']} armazenados, {storage_result['images_uploaded']} imagens")
            
            # Salva resultados locais se solicitado
            if save_results:
                self._save_results(final_products, report)
            
            return {
                'products': final_products,
                'report': report,
                'storage_result': storage_result,
                'execution_time': elapsed_time
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na análise completa: {e}")
            return {}

    def _save_results(self, products: List[Dict], report: Dict):
        """Salva os resultados da análise em arquivos locais."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("exports")
        output_dir.mkdir(exist_ok=True)
        
        # Salva produtos em CSV
        df = pd.DataFrame(products)
        products_filepath = output_dir / f"trending_products_{timestamp}.csv"
        df.to_csv(products_filepath, index=False)
        logger.info(f"Produtos trending salvos em: {products_filepath}")
        
        # Salva relatório em JSON
        report_filepath = output_dir / f"trending_report_{timestamp}.json"
        with open(report_filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Relatório trending salvo em: {report_filepath}")
