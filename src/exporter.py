"""
Sistema de exportação para diferentes formatos
Suporte para CSV, JSON, Excel e outros formatos
"""

import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from .models import Product, ImportResult
from .config import settings


class DataExporter:
    """Exportador de dados para diferentes formatos"""
    
    def __init__(self, export_dir: str = None):
        self.export_dir = Path(export_dir or settings.export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
    def _prepare_products_data(self, products: List[Product]) -> List[Dict[str, Any]]:
        """Prepara dados dos produtos para exportação - focado nos 4 campos principais"""
        data = []
        
        for product in products:
            for variation in product.variations:
                data.append({
                    'produto': variation.name,  # Nome do produto
                    'descricao': product.description or variation.name,  # Descrição
                    'imagem_original': variation.image_url or '',  # URL da imagem
                    'preco': variation.price,  # Preço
                    # Campos adicionais para contexto
                    'categoria': product.category,
                    'cor': variation.color,
                    'tamanho': variation.size,
                    'produto_base': product.base_name,
                    'total_variacoes': product.total_variations
                })
        
        return data
    
    def _prepare_summary_data(self, products: List[Product], import_result: ImportResult) -> Dict[str, Any]:
        """Prepara dados de resumo para exportação"""
        categories = {}
        for product in products:
            category = product.category or "Outros"
            if category not in categories:
                categories[category] = {
                    'product_count': 0,
                    'variation_count': 0,
                    'avg_price': 0,
                    'min_price': float('inf'),
                    'max_price': 0
                }
            
            categories[category]['product_count'] += 1
            categories[category]['variation_count'] += len(product.variations)
            
            prices = [v.price for v in product.variations]
            if prices:
                categories[category]['avg_price'] = sum(prices) / len(prices)
                categories[category]['min_price'] = min(categories[category]['min_price'], min(prices))
                categories[category]['max_price'] = max(categories[category]['max_price'], max(prices))
        
        # Converte inf para None para JSON
        for cat_data in categories.values():
            if cat_data['min_price'] == float('inf'):
                cat_data['min_price'] = None
        
        return {
            'import_summary': {
                'total_products': import_result.total_products,
                'total_variations': import_result.total_variations,
                'successful_imports': import_result.successful_imports,
                'failed_imports': import_result.failed_imports,
                'success_rate': import_result.success_rate,
                'import_duration': import_result.import_duration,
                'created_at': import_result.created_at.isoformat()
            },
            'categories': categories,
            'export_timestamp': datetime.now().isoformat()
        }
    
    def export_to_csv(self, products: List[Product], filename: str = None) -> str:
        """Exporta produtos para CSV"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"b2drop_products_{timestamp}.csv"
        
        filepath = self.export_dir / filename
        
        try:
            data = self._prepare_products_data(products)
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False, encoding='utf-8')
            
            logger.info(f"Exportação CSV concluída: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Erro na exportação CSV: {e}")
            raise
    
    def export_to_excel(self, products: List[Product], import_result: ImportResult, filename: str = None) -> str:
        """Exporta produtos para Excel com múltiplas abas"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"b2drop_products_{timestamp}.xlsx"
        
        filepath = self.export_dir / filename
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Aba 1: Produtos detalhados
                products_data = self._prepare_products_data(products)
                df_products = pd.DataFrame(products_data)
                df_products.to_excel(writer, sheet_name='Produtos', index=False)
                
                # Aba 2: Resumo por categoria
                summary_data = self._prepare_summary_data(products, import_result)
                categories_data = []
                for category, stats in summary_data['categories'].items():
                    categories_data.append({
                        'Categoria': category,
                        'Total de Produtos': stats['product_count'],
                        'Total de Variações': stats['variation_count'],
                        'Preço Médio': round(stats['avg_price'], 2) if stats['avg_price'] else 0,
                        'Preço Mínimo': stats['min_price'] if stats['min_price'] else 0,
                        'Preço Máximo': stats['max_price']
                    })
                
                df_categories = pd.DataFrame(categories_data)
                df_categories.to_excel(writer, sheet_name='Resumo por Categoria', index=False)
                
                # Aba 3: Estatísticas gerais
                general_stats = summary_data['import_summary']
                stats_data = [{'Métrica': k, 'Valor': v} for k, v in general_stats.items()]
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='Estatísticas', index=False)
            
            logger.info(f"Exportação Excel concluída: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Erro na exportação Excel: {e}")
            raise
    
    def export_to_json(self, products: List[Product], import_result: ImportResult, filename: str = None) -> str:
        """Exporta produtos para JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"b2drop_products_{timestamp}.json"
        
        filepath = self.export_dir / filename
        
        try:
            # Prepara dados completos
            products_data = self._prepare_products_data(products)
            summary_data = self._prepare_summary_data(products, import_result)
            
            export_data = {
                'metadata': summary_data,
                'products': products_data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"Exportação JSON concluída: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Erro na exportação JSON: {e}")
            raise
    
    def export_products_by_category(self, products: List[Product], format: str = 'csv') -> List[str]:
        """Exporta produtos separados por categoria"""
        categories = {}
        
        # Agrupa produtos por categoria
        for product in products:
            category = product.category or "Outros"
            if category not in categories:
                categories[category] = []
            categories[category].append(product)
        
        exported_files = []
        
        for category, category_products in categories.items():
            # Limpa nome da categoria para arquivo
            safe_category = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_category = safe_category.replace(' ', '_').lower()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"b2drop_{safe_category}_{timestamp}.{format}"
            
            try:
                if format == 'csv':
                    filepath = self.export_csv(category_products, filename)
                elif format == 'json':
                    # Cria ImportResult vazio para categoria
                    category_result = ImportResult(
                        total_products=len(category_products),
                        total_variations=sum(len(p.variations) for p in category_products)
                    )
                    filepath = self.export_json(category_products, category_result, filename)
                else:
                    logger.warning(f"Formato {format} não suportado para exportação por categoria")
                    continue
                
                exported_files.append(filepath)
                logger.info(f"Categoria {category} exportada: {filepath}")
                
            except Exception as e:
                logger.error(f"Erro ao exportar categoria {category}: {e}")
        
        return exported_files
    
    def export_csv(self, products: List[Product], filename: str) -> str:
        """Alias para export_to_csv"""
        return self.export_to_csv(products, filename)
    
    def export_json(self, products: List[Product], import_result: ImportResult, filename: str) -> str:
        """Alias para export_to_json"""
        return self.export_to_json(products, import_result, filename)
    
    def export_excel(self, products: List[Product], import_result: ImportResult, filename: str) -> str:
        """Alias para export_to_excel"""
        return self.export_to_excel(products, import_result, filename)
