# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from itemloaders.processors import TakeFirst, MapCompose, Compose
import re


def clean_price(value):
    """Limpa e converte preços para float"""
    if not value:
        return 0.0
    
    # Remove caracteres não numéricos, exceto vírgula e ponto
    cleaned = re.sub(r'[^\d,.]', '', str(value))
    
    # Converte vírgula para ponto (padrão brasileiro)
    cleaned = cleaned.replace(',', '.')
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def clean_text(value):
    """Limpa texto removendo espaços extras e caracteres inválidos"""
    if not value:
        return ""
    
    # Remove espaços extras e quebras de linha
    cleaned = re.sub(r'\s+', ' ', str(value).strip())
    return cleaned


def extract_product_id(value):
    """Extrai ID do produto de URLs ou strings"""
    if not value:
        return None
        
    # Procura por padrões de ID em URLs
    match = re.search(r'/product[s]?/(\d+)', str(value))
    if match:
        return match.group(1)
        
    # Se não encontrar, tenta extrair números
    numbers = re.findall(r'\d+', str(value))
    return numbers[0] if numbers else None


class B2DropProductItem(scrapy.Item):
    """Item principal para produtos do B2Drop"""
    
    # Identificadores únicos
    product_id = scrapy.Field(
        input_processor=MapCompose(extract_product_id),
        output_processor=TakeFirst()
    )
    sku = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Informações básicas do produto
    produto = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    descricao = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    categoria = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Preço e variações
    preco = scrapy.Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    preco_promocional = scrapy.Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    
    # Variações do produto
    cor = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    tamanho = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Imagens
    imagem_original = scrapy.Field(
        output_processor=TakeFirst()
    )
    imagens_adicionais = scrapy.Field()
    
    # Metadados
    url_produto = scrapy.Field(
        output_processor=TakeFirst()
    )
    disponibilidade = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Dados de processamento
    scraped_at = scrapy.Field()
    hash_produto = scrapy.Field()
    
    # Informações estruturadas
    produto_base = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    total_variacoes = scrapy.Field()


class B2DropCategoryItem(scrapy.Item):
    """Item para categorias do B2Drop"""
    
    categoria_id = scrapy.Field(
        input_processor=MapCompose(extract_product_id),
        output_processor=TakeFirst()
    )
    nome = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    url = scrapy.Field(
        output_processor=TakeFirst()
    )
    produtos_count = scrapy.Field()
    parent_category = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )


class B2DropStatsItem(scrapy.Item):
    """Item para estatísticas de scraping"""
    
    total_produtos = scrapy.Field()
    total_categorias = scrapy.Field()
    produtos_com_imagem = scrapy.Field()
    produtos_sem_preco = scrapy.Field()
    tempo_execucao = scrapy.Field()
    data_scraping = scrapy.Field()
    errors_count = scrapy.Field()
    warnings_count = scrapy.Field()