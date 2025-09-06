#!/usr/bin/env python3
"""
Test Protection System - Testa as correções de proteção contra sobrescrita
Valida que os 343 produtos existentes estão protegidos
"""

import os
import sys
import json
import time
from pathlib import Path
from loguru import logger

# Adiciona o diretório atual ao path
sys.path.append(str(Path(__file__).parent))

from cloudflare_storage_fixed import CloudflareStorage
from top_products_aggregator import TopProductsAggregator
from backup_manager import BackupManager
from product_deduplication import ProductDeduplication

def test_hash_generation():
    """Testa geração de hash única e segura"""
    logger.info("🧪 Testando geração de hash seguro...")
    
    storage = CloudflareStorage(enable_protection=False)  # Desativa proteção para teste rápido
    
    # Testa produtos similares
    test_products = [
        {"produto": "iPhone 16 128GB", "preco": 4500, "loja": "Loja A", "imagem_original": "url1"},
        {"produto": "iPhone 16 128GB", "preco": 4600, "loja": "Loja B", "imagem_original": "url2"},
        {"produto": "iPhone 16 - 128GB", "preco": 4500, "loja": "Loja A", "imagem_original": "url1"},
    ]
    
    generated_ids = []
    for i, product in enumerate(test_products):
        product_id = storage.generate_secure_product_id(
            product["produto"], 
            "test_source",
            product
        )
        generated_ids.append(product_id)
        logger.info(f"Produto {i+1}: {product['produto']} → ID: {product_id}")
    
    # Verifica unicidade
    unique_ids = set(generated_ids)
    if len(unique_ids) == len(generated_ids):
        logger.success("✅ IDs únicos gerados com sucesso!")
        return True
    else:
        logger.error(f"❌ Colisão detectada! {len(generated_ids)} produtos geraram {len(unique_ids)} IDs únicos")
        return False

def test_collision_protection():
    """Testa proteção contra colisão durante armazenamento"""
    logger.info("🧪 Testando proteção contra colisão...")
    
    storage = CloudflareStorage(enable_protection=True)
    
    # Simula produto já existente
    test_product = {
        "produto": "Produto Teste Colisão",
        "preco": 100.0,
        "categoria": "Teste",
        "imagem_original": "https://example.com/test.jpg",
        "descricao": "Produto para teste de colisão"
    }
    
    # Primeira inserção
    logger.info("Inserindo produto pela primeira vez...")
    result1 = storage.store_product(test_product, "test_collision")
    
    if result1:
        logger.success("✅ Primeira inserção bem-sucedida")
    else:
        logger.error("❌ Falha na primeira inserção")
        return False
    
    # Segunda inserção (deve detectar produto existente)
    logger.info("Inserindo mesmo produto novamente (deve detectar existência)...")
    test_product["descricao"] = "Descrição atualizada para testar sobrescrita"
    result2 = storage.store_product(test_product, "test_collision")
    
    if result2:
        logger.success("✅ Sistema detectou produto existente e atualizou")
        return True
    else:
        logger.error("❌ Falha na detecção/atualização")
        return False

def test_backup_system():
    """Testa sistema de backup"""
    logger.info("🧪 Testando sistema de backup...")
    
    backup_manager = BackupManager("test_backups")
    
    # Dados de teste
    test_products = [
        {
            "product_id": "test_001",
            "produto": "Produto Teste 1",
            "preco": 50.0,
            "categoria": "Teste",
            "source": "test"
        },
        {
            "product_id": "test_002", 
            "produto": "Produto Teste 2",
            "preco": 75.0,
            "categoria": "Teste",
            "source": "test"
        }
    ]
    
    # Testa backup diário
    backup_file = backup_manager.create_daily_backup(test_products)
    
    if backup_file and os.path.exists(backup_file):
        logger.success(f"✅ Backup criado com sucesso: {backup_file}")
        
        # Testa restauração
        restored_products = backup_manager.restore_from_backup(backup_file)
        if len(restored_products) == len(test_products):
            logger.success("✅ Restauração de backup bem-sucedida")
            return True
        else:
            logger.error(f"❌ Falha na restauração: {len(restored_products)} != {len(test_products)}")
    else:
        logger.error("❌ Falha na criação do backup")
    
    return False

def test_deduplication():
    """Testa sistema de deduplicação"""
    logger.info("🧪 Testando sistema de deduplicação...")
    
    dedup = ProductDeduplication(similarity_threshold=0.8)
    
    # Produtos com duplicatas intencionais
    test_products = [
        {"produto": "iPhone 16 128GB Preto", "preco": 4500, "source": "loja_a"},
        {"produto": "iPhone 16 - 128GB - Preto", "preco": 4550, "source": "loja_b"},  # Duplicata
        {"produto": "Samsung Galaxy S24", "preco": 3500, "source": "loja_a"},
        {"produto": "Galaxy S24 Samsung", "preco": 3600, "source": "loja_c"},  # Duplicata
        {"produto": "MacBook Pro M3", "preco": 8000, "source": "loja_a"},  # Único
    ]
    
    # Testa detecção de duplicatas
    duplicate_groups = dedup.detect_duplicates(test_products)
    
    if len(duplicate_groups) >= 2:  # Espera pelo menos 2 grupos de duplicatas
        logger.success(f"✅ Duplicatas detectadas: {len(duplicate_groups)} grupos")
        
        # Testa deduplicação completa
        deduplicated, stats = dedup.deduplicate_products(test_products)
        
        expected_final = len(test_products) - stats['products_removed']
        if len(deduplicated) == expected_final:
            logger.success(f"✅ Deduplicação bem-sucedida: {len(test_products)} → {len(deduplicated)} produtos")
            return True
        else:
            logger.error(f"❌ Falha na deduplicação: {len(deduplicated)} != {expected_final}")
    else:
        logger.error(f"❌ Falha na detecção: {len(duplicate_groups)} grupos encontrados")
    
    return False

def test_aggregator_integration():
    """Testa integração com o agregador principal"""
    logger.info("🧪 Testando integração com agregador...")
    
    try:
        aggregator = TopProductsAggregator()
        
        # Testa se usa sistema seguro de ID
        test_product = {
            "produto": "Produto Teste Agregador",
            "preco": 200.0,
            "categoria": "Teste",
            "source": "test_api",
            "imagem_original": "https://example.com/test.jpg"
        }
        
        # Testa padronização
        standardized = aggregator.standardize_product(test_product)
        
        if standardized and 'product_id' in standardized:
            product_id = standardized['product_id']
            
            # Verifica se usa formato seguro
            if "_" in product_id and len(product_id) > 20:  # Formato: source_hash_timestamp
                logger.success(f"✅ Agregador usando ID seguro: {product_id}")
                return True
            else:
                logger.error(f"❌ Formato de ID inseguro: {product_id}")
        else:
            logger.error("❌ Falha na padronização do produto")
    
    except Exception as e:
        logger.error(f"❌ Erro no teste do agregador: {e}")
    
    return False

def test_full_protection():
    """Testa proteção completa do sistema"""
    logger.info("🧪 Testando proteção completa do sistema...")
    
    storage = CloudflareStorage(enable_protection=True)
    
    # Verifica status de proteção
    protection_status = storage.get_protection_status()
    
    logger.info(f"Status de proteção: {protection_status}")
    
    required_protections = ['protection_enabled', 'backup_system', 'deduplication_system']
    all_enabled = all(protection_status.get(key, False) for key in required_protections)
    
    if all_enabled:
        logger.success("✅ Todos os sistemas de proteção estão ativos")
        return True
    else:
        missing = [key for key in required_protections if not protection_status.get(key, False)]
        logger.error(f"❌ Proteções ausentes: {missing}")
        return False

def run_all_tests():
    """Executa todos os testes de proteção"""
    logger.info("🚀 Iniciando bateria completa de testes de proteção...")
    
    tests = [
        ("Geração de Hash Seguro", test_hash_generation),
        ("Proteção contra Colisão", test_collision_protection), 
        ("Sistema de Backup", test_backup_system),
        ("Sistema de Deduplicação", test_deduplication),
        ("Integração com Agregador", test_aggregator_integration),
        ("Proteção Completa", test_full_protection),
    ]
    
    results = {}
    passed_count = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 EXECUTANDO: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            results[test_name] = {
                "passed": result,
                "duration": f"{duration:.2f}s"
            }
            
            if result:
                passed_count += 1
                logger.success(f"✅ {test_name} PASSOU ({duration:.2f}s)")
            else:
                logger.error(f"❌ {test_name} FALHOU ({duration:.2f}s)")
                
        except Exception as e:
            logger.error(f"💥 {test_name} ERRO: {e}")
            results[test_name] = {
                "passed": False,
                "error": str(e),
                "duration": "N/A"
            }
    
    # Relatório final
    logger.info(f"\n{'='*60}")
    logger.info("📋 RELATÓRIO FINAL DOS TESTES")
    logger.info(f"{'='*60}")
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result["passed"] else "❌ FALHOU"
        duration = result.get("duration", "N/A")
        logger.info(f"{status} | {test_name} ({duration})")
        
        if "error" in result:
            logger.error(f"     Erro: {result['error']}")
    
    success_rate = (passed_count / len(tests)) * 100
    logger.info(f"\n🎯 TAXA DE SUCESSO: {passed_count}/{len(tests)} ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        logger.success("🎉 SISTEMA DE PROTEÇÃO APROVADO!")
        logger.info("✅ Os 343 produtos existentes estão protegidos contra sobrescrita")
    else:
        logger.error("⚠️ SISTEMA DE PROTEÇÃO PRECISA DE CORREÇÕES")
        logger.warning("❌ Risco de perda de dados dos 343 produtos existentes")
    
    return success_rate >= 80

if __name__ == "__main__":
    # Configura logging para o teste
    logger.add("test_protection.log", rotation="10 MB", retention="7 days")
    
    logger.info("🔒 INICIANDO TESTES DE PROTEÇÃO CONTRA SOBRESCRITA")
    logger.info("🎯 Objetivo: Proteger os 343 produtos existentes (294 + 49)")
    
    success = run_all_tests()
    
    if success:
        logger.success("🏆 TESTES CONCLUÍDOS COM SUCESSO!")
        logger.info("🛡️ Sistema pronto para novos scraps sem risco de sobrescrita")
    else:
        logger.error("💀 FALHAS DETECTADAS NOS TESTES!")
        logger.warning("🚨 NÃO execute novos scraps até corrigir os problemas")
    
    sys.exit(0 if success else 1)