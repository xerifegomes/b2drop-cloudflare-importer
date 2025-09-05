"""
Processador de dados para limpeza e normalização
Implementa validação e transformação de dados
"""

import re
import pandas as pd
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime

from .models import Product, ProductVariation, ImportResult, CategoryStats


class DataProcessor:
    """Processador de dados para limpeza e normalização"""
    
    def __init__(self):
        self.cleaned_data = []
        self.errors = []
        self.stats = {}
    
    def clean_product_name(self, name: str) -> str:
        """Limpa e normaliza nome do produto"""
        if not name:
            return ""
        
        # Remove caracteres especiais excessivos
        cleaned = re.sub(r'[^\w\s\-\.\(\)]', ' ', name)
        
        # Remove espaços múltiplos
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Remove espaços no início e fim
        cleaned = cleaned.strip()
        
        # Capitaliza primeira letra de cada palavra
        cleaned = ' '.join(word.capitalize() for word in cleaned.split())
        
        return cleaned
    
    def validate_price(self, price: float) -> bool:
        """Valida se o preço é válido"""
        return isinstance(price, (int, float)) and price >= 0 and price <= 10000
    
    def clean_price(self, price: Any) -> float:
        """Limpa e normaliza preço"""
        if isinstance(price, str):
            # Remove caracteres não numéricos exceto ponto e vírgula
            cleaned = re.sub(r'[^\d,.]', '', price)
            # Substitui vírgula por ponto
            cleaned = cleaned.replace(',', '.')
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        elif isinstance(price, (int, float)):
            return float(price)
        else:
            return 0.0
    
    def normalize_category(self, category: str) -> str:
        """Normaliza categoria do produto"""
        if not category:
            return "Outros"
        
        category_mapping = {
            'eletrônicos': 'Eletrônicos',
            'eletronicos': 'Eletrônicos',
            'casa e organização': 'Casa e Organização',
            'casa': 'Casa e Organização',
            'saúde e bem-estar': 'Saúde e Bem-estar',
            'saude': 'Saúde e Bem-estar',
            'pet shop': 'Pet Shop',
            'pets': 'Pet Shop',
            'moda e acessórios': 'Moda e Acessórios',
            'moda': 'Moda e Acessórios',
            'cozinha': 'Cozinha',
            'limpeza': 'Limpeza',
            'esportes': 'Esportes',
            'outros': 'Outros'
        }
        
        category_lower = category.lower().strip()
        return category_mapping.get(category_lower, category.title())
    
    def detect_duplicates(self, products: List[Product]) -> List[Product]:
        """Detecta e remove produtos duplicados"""
        seen_products = {}
        unique_products = []
        
        for product in products:
            # Cria chave única baseada no nome base e categoria
            key = f"{product.base_name.lower()}_{product.category.lower()}"
            
            if key not in seen_products:
                seen_products[key] = product
                unique_products.append(product)
            else:
                # Merge variações de produtos duplicados
                existing_product = seen_products[key]
                for variation in product.variations:
                    existing_product.add_variation(variation)
                logger.info(f"Produto duplicado mesclado: {product.base_name}")
        
        return unique_products
    
    def validate_product(self, product: Product) -> bool:
        """Valida integridade do produto"""
        errors = []
        
        # Validações básicas
        if not product.base_name or len(product.base_name.strip()) < 3:
            errors.append("Nome do produto muito curto ou vazio")
        
        if not product.variations:
            errors.append("Produto sem variações")
        
        # Valida preços
        for variation in product.variations:
            if not self.validate_price(variation.price):
                errors.append(f"Preço inválido na variação: {variation.name}")
        
        if errors:
            logger.warning(f"Erros de validação no produto {product.base_name}: {errors}")
            self.errors.extend(errors)
            return False
        
        return True
    
    def process_products(self, products: List[Product]) -> List[Product]:
        """Processa lista de produtos com limpeza e validação"""
        logger.info(f"Processando {len(products)} produtos")
        
        processed_products = []
        
        for product in products:
            try:
                # Limpa dados do produto
                product.base_name = self.clean_product_name(product.base_name)
                product.category = self.normalize_category(product.category)
                
                # Limpa variações
                for variation in product.variations:
                    variation.name = self.clean_product_name(variation.name)
                    variation.price = self.clean_price(variation.price)
                
                # Valida produto
                if self.validate_product(product):
                    processed_products.append(product)
                else:
                    logger.warning(f"Produto rejeitado na validação: {product.base_name}")
                    
            except Exception as e:
                logger.error(f"Erro ao processar produto {product.base_name}: {e}")
                self.errors.append(f"Erro ao processar {product.base_name}: {str(e)}")
        
        # Remove duplicatas
        processed_products = self.detect_duplicates(processed_products)
        
        logger.info(f"Produtos processados com sucesso: {len(processed_products)}")
        logger.info(f"Erros encontrados: {len(self.errors)}")
        
        return processed_products
    
    def generate_stats(self, products: List[Product]) -> Dict[str, Any]:
        """Gera estatísticas dos produtos processados"""
        if not products:
            return {}
        
        total_products = len(products)
        total_variations = sum(len(p.variations) for p in products)
        
        # Estatísticas por categoria
        category_stats = {}
        for product in products:
            category = product.category or "Outros"
            if category not in category_stats:
                category_stats[category] = {
                    'product_count': 0,
                    'variation_count': 0,
                    'prices': []
                }
            
            category_stats[category]['product_count'] += 1
            category_stats[category]['variation_count'] += len(product.variations)
            category_stats[category]['prices'].extend([v.price for v in product.variations])
        
        # Calcula estatísticas finais
        for category, stats in category_stats.items():
            prices = stats['prices']
            if prices:
                stats['avg_price'] = sum(prices) / len(prices)
                stats['min_price'] = min(prices)
                stats['max_price'] = max(prices)
            else:
                stats['avg_price'] = 0
                stats['min_price'] = 0
                stats['max_price'] = 0
            
            del stats['prices']  # Remove lista de preços
        
        # Preços gerais
        all_prices = []
        for product in products:
            all_prices.extend([v.price for v in product.variations])
        
        general_stats = {
            'total_products': total_products,
            'total_variations': total_variations,
            'avg_price': sum(all_prices) / len(all_prices) if all_prices else 0,
            'min_price': min(all_prices) if all_prices else 0,
            'max_price': max(all_prices) if all_prices else 0,
            'categories': category_stats,
            'processing_errors': len(self.errors)
        }
        
        self.stats = general_stats
        return general_stats
    
    def create_import_result(self, products: List[Product], duration: float) -> ImportResult:
        """Cria resultado da importação"""
        total_products = len(products)
        total_variations = sum(len(p.variations) for p in products)
        
        return ImportResult(
            total_products=total_products,
            total_variations=total_variations,
            successful_imports=total_products,
            failed_imports=len(self.errors),
            errors=self.errors,
            import_duration=duration
        )
