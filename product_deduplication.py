#!/usr/bin/env python3
"""
Product Deduplication - Sistema Inteligente de Deduplicação de Produtos
Detecta e resolve duplicatas entre diferentes fontes e execuções
"""

import re
import hashlib
from typing import Dict, Any, List, Tuple, Set
from loguru import logger
import difflib
from collections import defaultdict

class ProductDeduplication:
    """Sistema inteligente de deduplicação de produtos"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.normalization_patterns = [
            (r'\s+', ' '),  # Múltiplos espaços
            (r'[^\w\s]', ''),  # Remove pontuação
            (r'\b(kit|pack|conjunto|unidade|un|pç|peça)\b', ''),  # Remove palavras comuns
            (r'\b\d+\s*(gb|mb|kg|g|ml|l|cm|mm|m|pol|polegadas)\b', ''),  # Remove medidas
            (r'\b(preto|branco|azul|vermelho|verde|amarelo|rosa|roxo|cinza)\b', ''),  # Remove cores
        ]
        
        logger.info(f"🔍 Sistema de Deduplicação inicializado (threshold: {similarity_threshold})")

    def normalize_product_name(self, product_name: str) -> str:
        """Normaliza nome do produto para comparação"""
        if not product_name:
            return ""
        
        normalized = product_name.lower().strip()
        
        # Aplica padrões de normalização
        for pattern, replacement in self.normalization_patterns:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        # Remove espaços extras e converte para minúsculas
        normalized = ' '.join(normalized.split())
        
        return normalized

    def calculate_similarity(self, name1: str, name2: str) -> float:
        """Calcula similaridade entre dois nomes de produtos"""
        norm1 = self.normalize_product_name(name1)
        norm2 = self.normalize_product_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Usa SequenceMatcher para calcular similaridade
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        return similarity

    def detect_duplicates(self, products: List[Dict]) -> Dict[str, List[Dict]]:
        """Detecta grupos de produtos duplicados"""
        logger.info(f"🔍 Iniciando detecção de duplicatas em {len(products)} produtos...")
        
        duplicate_groups = defaultdict(list)
        processed_indices = set()
        
        for i, product1 in enumerate(products):
            if i in processed_indices:
                continue
                
            current_group = [product1]
            processed_indices.add(i)
            
            name1 = product1.get('produto', '')
            if not name1:
                continue
            
            # Compara com produtos restantes
            for j, product2 in enumerate(products[i+1:], i+1):
                if j in processed_indices:
                    continue
                    
                name2 = product2.get('produto', '')
                if not name2:
                    continue
                
                similarity = self.calculate_similarity(name1, name2)
                
                if similarity >= self.similarity_threshold:
                    current_group.append(product2)
                    processed_indices.add(j)
            
            # Se encontrou duplicatas, adiciona ao grupo
            if len(current_group) > 1:
                group_key = f"group_{len(duplicate_groups) + 1}"
                duplicate_groups[group_key] = current_group
                logger.warning(f"🔄 Duplicatas encontradas - {group_key}: {len(current_group)} produtos similares")
        
        logger.info(f"✅ Detecção concluída: {len(duplicate_groups)} grupos de duplicatas encontrados")
        return dict(duplicate_groups)

    def resolve_duplicate_group(self, duplicate_group: List[Dict]) -> Dict:
        """Resolve um grupo de duplicatas escolhendo o melhor produto"""
        if len(duplicate_group) == 1:
            return duplicate_group[0]
        
        logger.debug(f"🔧 Resolvendo grupo de {len(duplicate_group)} duplicatas...")
        
        best_product = None
        best_score = -1
        
        for product in duplicate_group:
            score = self._calculate_product_quality_score(product)
            
            if score > best_score:
                best_score = score
                best_product = product
        
        # Mescla informações úteis dos produtos duplicados
        merged_product = self._merge_product_data(best_product, duplicate_group)
        
        logger.debug(f"✅ Melhor produto selecionado (score: {best_score:.2f}): {merged_product.get('produto', '')[:50]}...")
        
        return merged_product

    def _calculate_product_quality_score(self, product: Dict) -> float:
        """Calcula score de qualidade do produto para resolver duplicatas"""
        score = 0.0
        
        # Score por completude de dados
        required_fields = ['produto', 'preco', 'categoria', 'imagem_original']
        for field in required_fields:
            if product.get(field):
                score += 1.0
        
        # Score por qualidade dos dados
        if product.get('descricao') and len(product.get('descricao', '')) > 50:
            score += 0.5
        
        if product.get('trending_score', 0) > 8:
            score += 1.0
        elif product.get('trending_score', 0) > 6:
            score += 0.5
        
        # Prefere produtos com preço válido
        preco = product.get('preco', 0)
        if isinstance(preco, (int, float)) and preco > 0:
            score += 0.5
        
        # Score por fonte (algumas fontes podem ser mais confiáveis)
        source = product.get('source', '')
        if source == 'google_trending':
            score += 0.3
        elif source == 'b2drop':
            score += 0.2
        
        # Penaliza produtos muito antigos
        if product.get('created_at'):
            import time
            age_days = (time.time() - product.get('created_at', 0)) / (24 * 3600)
            if age_days > 30:
                score -= 0.2
        
        return score

    def _merge_product_data(self, best_product: Dict, all_products: List[Dict]) -> Dict:
        """Mescla dados úteis de produtos duplicados"""
        merged = best_product.copy()
        
        # Lista de fontes alternativas
        alternative_sources = []
        all_images = set()
        all_urls = set()
        
        for product in all_products:
            if product != best_product:
                # Coleta fontes alternativas
                source_info = {
                    'source': product.get('source', ''),
                    'loja': product.get('loja', ''),
                    'preco': product.get('preco', 0),
                    'url_produto': product.get('url_produto', '')
                }
                alternative_sources.append(source_info)
                
                # Coleta imagens alternativas
                if product.get('imagem_original'):
                    all_images.add(product.get('imagem_original'))
                
                # Coleta URLs alternativas
                if product.get('url_produto'):
                    all_urls.add(product.get('url_produto'))
        
        # Adiciona informações mescladas
        merged['alternative_sources'] = alternative_sources
        merged['alternative_images'] = list(all_images)
        merged['alternative_urls'] = list(all_urls)
        merged['duplicate_count'] = len(all_products)
        merged['merge_timestamp'] = int(time.time())
        
        return merged

    def deduplicate_products(self, products: List[Dict]) -> Tuple[List[Dict], Dict]:
        """Executa processo completo de deduplicação"""
        logger.info(f"🚀 Iniciando deduplicação completa de {len(products)} produtos...")
        
        # Detecta duplicatas
        duplicate_groups = self.detect_duplicates(products)
        
        # Resolve duplicatas
        deduplicated_products = []
        resolution_stats = {
            'original_count': len(products),
            'duplicate_groups': len(duplicate_groups),
            'products_removed': 0,
            'products_merged': 0
        }
        
        # Cria índice de produtos que estão em grupos de duplicatas
        products_in_groups = set()
        for group in duplicate_groups.values():
            for product in group:
                products_in_groups.add(id(product))
        
        # Adiciona produtos únicos (não duplicados)
        for product in products:
            if id(product) not in products_in_groups:
                deduplicated_products.append(product)
        
        # Resolve grupos de duplicatas
        for group_key, duplicate_group in duplicate_groups.items():
            resolved_product = self.resolve_duplicate_group(duplicate_group)
            deduplicated_products.append(resolved_product)
            resolution_stats['products_merged'] += 1
            resolution_stats['products_removed'] += len(duplicate_group) - 1
        
        # Atualiza estatísticas finais
        resolution_stats['final_count'] = len(deduplicated_products)
        resolution_stats['reduction_percentage'] = (
            (resolution_stats['original_count'] - resolution_stats['final_count']) / 
            resolution_stats['original_count'] * 100
        )
        
        logger.success(f"✅ Deduplicação concluída:")
        logger.info(f"   📊 {resolution_stats['original_count']} → {resolution_stats['final_count']} produtos")
        logger.info(f"   🔄 {resolution_stats['duplicate_groups']} grupos de duplicatas resolvidos")
        logger.info(f"   📉 {resolution_stats['reduction_percentage']:.1f}% de redução")
        
        return deduplicated_products, resolution_stats

    def find_potential_duplicates_by_price(self, products: List[Dict], price_tolerance: float = 0.05) -> List[Tuple]:
        """Encontra potenciais duplicatas baseado no preço"""
        price_groups = defaultdict(list)
        
        for product in products:
            preco = product.get('preco', 0)
            if preco > 0:
                # Agrupa por faixa de preço
                price_key = round(preco / (1 + price_tolerance))
                price_groups[price_key].append(product)
        
        potential_duplicates = []
        for price_key, group in price_groups.items():
            if len(group) > 1:
                # Verifica similaridade de nomes dentro do grupo de preço
                for i, product1 in enumerate(group):
                    for product2 in group[i+1:]:
                        similarity = self.calculate_similarity(
                            product1.get('produto', ''),
                            product2.get('produto', '')
                        )
                        if similarity >= self.similarity_threshold:
                            potential_duplicates.append((product1, product2, similarity))
        
        return potential_duplicates

import time