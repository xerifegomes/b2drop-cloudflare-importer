"""
Modelos de dados para o B2Drop Importer
Define as estruturas de dados para produtos e variações
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
import re


class ProductVariation(BaseModel):
    """Modelo para variação de produto"""
    
    variation_id: str = Field(..., description="ID único da variação")
    name: str = Field(..., description="Nome da variação")
    color: Optional[str] = Field(None, description="Cor da variação")
    size: Optional[str] = Field(None, description="Tamanho da variação")
    price: float = Field(..., description="Preço da variação")
    sku: Optional[str] = Field(None, description="SKU da variação")
    image_url: Optional[str] = Field(None, description="URL da imagem")
    in_stock: bool = Field(default=True, description="Disponibilidade")
    
    @validator('price')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError('Preço deve ser positivo')
        return v


class Product(BaseModel):
    """Modelo principal para produto"""
    
    product_id: str = Field(..., description="ID único do produto")
    base_name: str = Field(..., description="Nome base do produto")
    category: Optional[str] = Field(None, description="Categoria do produto")
    description: Optional[str] = Field(None, description="Descrição do produto")
    brand: Optional[str] = Field(None, description="Marca do produto")
    min_price: float = Field(..., description="Menor preço entre variações")
    max_price: float = Field(..., description="Maior preço entre variações")
    variations: List[ProductVariation] = Field(default_factory=list)
    total_variations: int = Field(default=0, description="Total de variações")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @validator('variations')
    def validate_variations(cls, v):
        if not v:
            raise ValueError('Produto deve ter pelo menos uma variação')
        return v
    
    @validator('total_variations')
    def validate_total_variations(cls, v, values):
        if 'variations' in values and v != len(values['variations']):
            return len(values['variations'])
        return v
    
    def add_variation(self, variation: ProductVariation) -> None:
        """Adiciona uma variação ao produto"""
        self.variations.append(variation)
        self.total_variations = len(self.variations)
        self._update_price_range()
        self.updated_at = datetime.now()
    
    def _update_price_range(self) -> None:
        """Atualiza faixa de preços baseada nas variações"""
        if self.variations:
            prices = [v.price for v in self.variations]
            self.min_price = min(prices)
            self.max_price = max(prices)


class ImportResult(BaseModel):
    """Resultado da importação"""
    
    total_products: int = Field(default=0)
    total_variations: int = Field(default=0)
    successful_imports: int = Field(default=0)
    failed_imports: int = Field(default=0)
    errors: List[str] = Field(default_factory=list)
    import_duration: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso da importação"""
        if self.total_products == 0:
            return 0.0
        return (self.successful_imports / self.total_products) * 100


class CategoryStats(BaseModel):
    """Estatísticas por categoria"""
    
    category_name: str
    product_count: int
    variation_count: int
    avg_price: float
    min_price: float
    max_price: float
