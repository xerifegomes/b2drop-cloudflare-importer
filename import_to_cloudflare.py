#!/usr/bin/env python3
"""
Import to Cloudflare - Script final e refatorado
Importa produtos B2Drop e armazena no Cloudflare usando a classe centralizada.
"""

import sys
import argparse
from pathlib import Path
from loguru import logger
import pandas as pd

# Adiciona o diretório src ao path
sys.path.append(str(Path(__file__).parent / "src"))

from src.importer import B2DropImporter
from cloudflare_storage_fixed import CloudflareStorage


def run_import(storage: CloudflareStorage):
    """Executa o processo completo de importação e armazenamento."""
    logger.info("📥 Etapa 1: Importando produtos do B2Drop...")
    importer = B2DropImporter()
    result = importer.import_catalog(export_format='csv')
    
    if not result['success'] or not result['export_files']:
        logger.error(f"❌ Falha na importação do B2Drop: {result.get('error')}")
        return False

    logger.info("☁️ Etapa 2: Enviando dados para o Cloudflare...")
    df = pd.read_csv(result['export_files'][0])
    storage_result = storage.store_products_batch(df)
    
    logger.info("📊 Relatório Final de Armazenamento:")
    logger.info(f"   • Total de produtos para processar: {storage_result['total_products']}")
    logger.info(f"   • Uploads bem-sucedidos: {storage_result['successful_uploads']}")
    logger.info(f"   • Uploads com falha: {storage_result['failed_uploads']}")
    return storage_result['failed_uploads'] == 0

def list_products(storage: CloudflareStorage, limit: int):
    """Lista produtos armazenados."""
    logger.info(f"📋 Listando os primeiros {limit} produtos do Cloudflare KV...")
    products = storage.list_products(limit=limit)
    if not products:
        logger.warning("Nenhum produto encontrado.")
        return

    for i, product in enumerate(products, 1):
        logger.info(f"{i}. {product.get('produto', 'N/A')} (Preço: R$ {product.get('preco', 0)})")
        logger.info(f"   - Imagem Original: {product.get('imagem_original', 'N/A')}")
        logger.info(f"   - Imagem R2: {product.get('imagem_r2', 'N/A')}")

def show_stats(storage: CloudflareStorage):
    """Exibe estatísticas dos produtos armazenados."""
    logger.info("📊 Buscando estatísticas...")
    stats = storage.get_statistics()
    if not stats or stats['total'] == 0:
        logger.warning("Nenhuma estatística para mostrar.")
        return
    
    logger.info(f"   • Total de produtos: {stats['total']}")
    logger.info(f"   • Preço médio: R$ {stats.get('preco_medio', 0):.2f}")
    logger.info(f"   • Preço mínimo: R$ {stats.get('preco_min', 0):.2f}")
    logger.info(f"   • Preço máximo: R$ {stats.get('preco_max', 0):.2f}")
    if stats.get('categorias'):
        logger.info("   • Produtos por Categoria:")
        for cat, count in stats['categorias'].items():
            logger.info(f"     - {cat}: {count}")

def main():
    """Função principal para orquestrar ações via CLI."""
    parser = argparse.ArgumentParser(description="Gerenciador de Importação B2Drop para Cloudflare.")
    parser.add_argument('action', choices=['import', 'list', 'stats'], help='Ação a ser executada.')
    parser.add_argument('--limit', type=int, default=10, help='Limite de resultados para a ação "list".')
    args = parser.parse_args()

    try:
        storage = CloudflareStorage()
        if not storage.init_r2_bucket():
            logger.error("Não foi possível inicializar o armazenamento R2. Verifique as permissões e a configuração.")
            sys.exit(1)

        if args.action == 'import':
            run_import(storage)
        elif args.action == 'list':
            list_products(storage, args.limit)
        elif args.action == 'stats':
            show_stats(storage)

    except Exception as e:
        logger.error(f"❌ Ocorreu um erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()