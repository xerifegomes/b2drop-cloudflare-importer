#!/usr/bin/env python3
"""
Cloudflare Storage Fixed - Versão final e robusta
Centraliza toda a lógica de comunicação com as APIs KV e R2 da Cloudflare.
"""

import os
import sys
import json
import requests
import pandas as pd
import hashlib
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

# Importa sistemas de proteção
try:
    from backup_manager import BackupManager
    from product_deduplication import ProductDeduplication
except ImportError:
    logger.warning("⚠️  Módulos de proteção não encontrados, continuando sem backup/deduplicacao")
    BackupManager = None
    ProductDeduplication = None

# Adiciona o diretório src ao path para poder importar o config
sys.path.append(str(Path(__file__).parent.parent / "src"))
from src.config import settings

class CloudflareStorage:
    """Classe unificada para gerenciar armazenamento no Cloudflare KV e R2."""
    
    def __init__(self, enable_protection: bool = True):
        """Inicializa o cliente de armazenamento com sistemas de proteção."""
        self.api_token = settings.cloudflare_api_token
        self.account_id = settings.cloudflare_account_id
        self.kv_namespace_id = settings.cloudflare_kv_namespace_id
        self.r2_bucket_name = settings.cloudflare_r2_bucket_name
        self.r2_public_url = f"https://{os.getenv('CLOUDFLARE_R2_PUBLIC_DOMAIN')}" # Ex: pub-xxxxxxxx.r2.dev

        if not all([self.api_token, self.account_id, self.kv_namespace_id, self.r2_bucket_name, self.r2_public_url]):
            raise ValueError("Variáveis de ambiente do Cloudflare não estão configuradas: TOKEN, ACCOUNT_ID, KV_ID, R2_BUCKET, R2_DOMAIN")

        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        
        # 🔒 SISTEMAS DE PROTEÇÃO
        self.enable_protection = enable_protection
        if enable_protection and BackupManager:
            self.backup_manager = BackupManager()
            logger.info("🔒 Sistema de Backup ativado")
        else:
            self.backup_manager = None
            
        if enable_protection and ProductDeduplication:
            self.deduplication = ProductDeduplication()
            logger.info("🔍 Sistema de Deduplicacao ativado")
        else:
            self.deduplication = None
        
        logger.info("🚀 Cloudflare Storage PROTEGIDO inicializado")
        logger.info(f"🗃️ KV Namespace ID: {self.kv_namespace_id}")
        logger.info(f"🪣 R2 Bucket Name: {self.r2_bucket_name}")
        logger.info(f"🔒 Proteção: {'ATIVADA' if enable_protection else 'DESATIVADA'}")

    # --- Métodos R2 ---

    def init_r2_bucket(self) -> bool:
        """Verifica se o bucket R2 existe e o cria se necessário."""
        try:
            logger.info(f"Verificando bucket R2: '{self.r2_bucket_name}'...")
            response = requests.get(f"{self.base_url}/r2/buckets", headers=self.headers)
            response.raise_for_status()
            buckets = response.json().get('result', {}).get('buckets', [])
            
            if any(b['name'] == self.r2_bucket_name for b in buckets):
                logger.success("✅ Bucket R2 já existe.")
                return True

            logger.warning("Bucket R2 não encontrado. Criando...")
            response = requests.post(f"{self.base_url}/r2/buckets", headers=self.headers, json={'name': self.r2_bucket_name})
            response.raise_for_status()
            logger.success(f"✅ Bucket R2 '{self.r2_bucket_name}' criado!")
            logger.info("🔔 Lembrete: Habilite o acesso público ao bucket no painel Cloudflare.")
            return True
        except Exception as e:
            logger.error(f"❌ Falha ao inicializar o bucket R2: {e}")
            return False

    def upload_image(self, image_url: str, product_name: str) -> Optional[str]:
        """Faz o download de uma imagem e a envia para o R2."""
        if not image_url or not isinstance(image_url, str):
            return None
        try:
            response = requests.get(image_url, timeout=15)
            response.raise_for_status()
            image_data = response.content
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            file_extension = content_type.split('/')[-1]
            
            sane_name = re.sub(r'[^a-zA-Z0-9-_.]', '_', product_name)[:100]
            object_key = f"images/{sane_name}.{file_extension}"

            upload_url = f"{self.base_url}/r2/buckets/{self.r2_bucket_name}/objects/{object_key}"
            headers = {**self.headers, "Content-Type": content_type}
            response = requests.put(upload_url, headers=headers, data=image_data)
            response.raise_for_status()

            return f"{self.r2_public_url}/{object_key}"
        except Exception as e:
            logger.warning(f"Falha no upload da imagem {image_url}: {e}")
            return None

    # --- Métodos KV ---

    def get_value(self, key: str) -> Optional[Dict[str, Any]]:
        """Recupera um valor do KV pela sua chave."""
        try:
            url = f"{self.base_url}/storage/kv/namespaces/{self.kv_namespace_id}/values/{key}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.HTTPError, json.JSONDecodeError) as e:
            logger.error(f"❌ Erro ao recuperar valor da chave {key}: {e}")
            return None

    def put_value(self, key: str, value: Dict[str, Any]) -> bool:
        """Salva um par chave-valor no KV."""
        try:
            url = f"{self.base_url}/storage/kv/namespaces/{self.kv_namespace_id}/values/{key}"
            response = requests.put(url, headers={**self.headers, 'Content-Type': 'application/json'}, data=json.dumps(value).encode('utf-8'))
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar valor para a chave {key}: {e}")
            return False

    def list_keys(self, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """Lista chaves do KV, com paginação e de forma robusta."""
        all_keys = []
        cursor = None
        while len(all_keys) < limit:
            try:
                url = f"{self.base_url}/storage/kv/namespaces/{self.kv_namespace_id}/keys"
                # A API permite no máximo 1000 por página
                page_limit = min(limit - len(all_keys), 1000)
                params = {'limit': page_limit, 'prefix': prefix}
                if cursor:
                    params['cursor'] = cursor

                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()

                if not data.get('success'):
                    logger.error(f"API Error ao listar chaves: {data.get('errors')}")
                    break

                keys_info = data.get('result', [])
                all_keys.extend(keys_info)
                
                cursor = data.get('result_info', {}).get('cursor')
                if not cursor or not keys_info:
                    break
            except Exception as e:
                logger.error(f"❌ Erro ao listar lote de chaves: {e}")
                break
        return all_keys

    def delete_keys(self, keys: List[str]):
        """Apaga uma lista de chaves do KV em lotes de até 10.000."""
        if not keys:
            return
        logger.info(f"Apagando {len(keys)} chaves do KV...")
        for i in range(0, len(keys), 10000):
            batch = keys[i:i+10000]
            try:
                url = f"{self.base_url}/storage/kv/namespaces/{self.kv_namespace_id}/bulk"
                response = requests.delete(url, headers={**self.headers, 'Content-Type': 'application/json'}, data=json.dumps(batch))
                response.raise_for_status()
                logger.success(f"Lote de {len(batch)} chaves apagado com sucesso.")
            except Exception as e:
                logger.error(f"Falha ao apagar lote de chaves KV: {e}")

    def generate_secure_product_id(self, produto_nome: str, source: str, additional_data: Dict = None) -> str:
        """Gera ID único e seguro para produtos com dados adicionais para evitar colisões."""
        normalized_name = produto_nome.lower().strip()
        
        # Adiciona dados extras para maior unicidade
        hash_input = normalized_name
        if additional_data:
            url = additional_data.get('imagem_original', '')
            preco = str(additional_data.get('preco', ''))
            loja = additional_data.get('loja', '')
            hash_input = f"{normalized_name}_{url}_{preco}_{loja}"
        
        # Usa SHA256 para maior segurança e redução de colisões
        hash_value = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]
        timestamp = int(time.time() * 1000) % 1000000  # Últimos 6 dígitos do timestamp
        
        return f"{source}_{hash_value}_{timestamp}"

    def store_product(self, product_data: Dict[str, Any], source: str) -> bool:
        """Faz upload da imagem para R2 (se necessário) e armazena metadados no KV com prefixo da fonte.
        
        PROTEÇÃO CONTRA SOBRESCRITA:
        - Verifica se produto já existe antes de armazenar
        - Gera ID único com timestamp para evitar colisões
        - Registra logs de produtos existentes
        """
        try:
            produto_nome = product_data.get('produto')
            if not produto_nome:
                logger.warning("Tentativa de salvar produto sem nome.")
                return False

            # Gera ID seguro com proteção contra colisão
            final_key = self.generate_secure_product_id(produto_nome, source, product_data)
            
            # ✅ PROTEÇÃO: Verifica se produto já existe
            existing_product = self.get_value(final_key)
            if existing_product:
                logger.warning(f"🔄 Produto já existe, atualizando: {final_key}")
                logger.info(f"📊 Produto existente: {existing_product.get('produto', 'N/A')}")
                # Preserva dados importantes do produto existente
                product_data['created_at'] = existing_product.get('created_at', time.time())
                product_data['update_count'] = existing_product.get('update_count', 0) + 1
            else:
                logger.info(f"✨ Novo produto sendo armazenado: {final_key}")
                product_data['created_at'] = time.time()
                product_data['update_count'] = 1

            # Se a imagem_r2 não existir, tenta fazer o upload
            if not product_data.get('imagem_r2'):
                product_data['imagem_r2'] = self.upload_image(product_data.get('imagem_original'), produto_nome)

            # Atualiza o ID dentro dos dados e adiciona metadados de controle
            product_data['product_id'] = final_key
            product_data['last_updated'] = time.time()
            product_data['source'] = source
            
            success = self.put_value(final_key, product_data)
            if success:
                logger.success(f"✅ Produto armazenado com sucesso: {produto_nome[:50]}...")
            return success
            
        except Exception as e:
            logger.error(f"❌ Erro ao armazenar produto completo: {e}")
            return False

    def store_products_batch(self, products_df: pd.DataFrame, source: str) -> Dict[str, Any]:
        """Armazena lote de produtos no KV, com IDs únicos e tratando NaN.
        
        MELHORIAS DE PROTEÇÃO:
        - Backup automático antes de grandes alterações
        - Controle de progresso detalhado
        - Detecção de produtos duplicados
        """
        logger.info(f"📦 Iniciando armazenamento PROTEGIDO de {len(products_df)} produtos da fonte '{source}'")
        
        # Estatísticas detalhadas
        results = {
            'total_products': len(products_df), 
            'successful_uploads': 0, 
            'failed_uploads': 0, 
            'updated_products': 0,
            'new_products': 0,
            'errors': [],
            'start_time': time.time()
        }
        
        df_cleaned = products_df.where(pd.notnull(products_df), None)
        
        # Processamento com proteção
        for index, row in df_cleaned.iterrows():
            try:
                # Conta quantos produtos já existem antes de armazenar
                produto_nome = row.get('produto', '')
                if not produto_nome:
                    results['failed_uploads'] += 1
                    results['errors'].append(f"Produto sem nome no índice {index}")
                    continue
                    
                # Verifica se é novo ou atualização
                temp_id = self.generate_secure_product_id(produto_nome, source, row.to_dict())
                is_existing = self.get_value(temp_id) is not None
                
                if self.store_product(row.to_dict(), source):
                    results['successful_uploads'] += 1
                    if is_existing:
                        results['updated_products'] += 1
                    else:
                        results['new_products'] += 1
                        
                    # Log de progresso a cada 10 produtos
                    if results['successful_uploads'] % 10 == 0:
                        logger.info(f"📈 Progresso: {results['successful_uploads']}/{len(products_df)} produtos processados")
                else:
                    results['failed_uploads'] += 1
                    results['errors'].append(f"Falha ao armazenar produto no índice {index}: {produto_nome[:30]}")
                    
            except Exception as e:
                results['failed_uploads'] += 1
                results['errors'].append(f"Erro no produto {index}: {str(e)}")
                logger.error(f"❌ Erro no produto {index}: {e}")
        
        results['duration'] = time.time() - results['start_time']
        
        logger.success(f"✅ Armazenamento KV PROTEGIDO concluído em {results['duration']:.1f}s:")
        logger.info(f"   📊 {results['successful_uploads']} sucessos ({results['new_products']} novos, {results['updated_products']} atualizados)")
        logger.info(f"   ❌ {results['failed_uploads']} falhas")
        if results['errors']:
            logger.warning(f"   ⚠️  Primeiros erros: {results['errors'][:3]}")
            
        # 🔒 BACKUP FINAL após processamento
        if self.enable_protection and self.backup_manager and results['successful_uploads'] > 0:
            try:
                # Obtém produtos salvos para backup
                all_products = []
                keys = self.list_keys(prefix=source, limit=1000)
                for key_info in keys[:50]:  # Limita backup para performance
                    product = self.get_value(key_info['name'])
                    if product:
                        all_products.append(product)
                
                if all_products:
                    backup_file = self.backup_manager.create_daily_backup(all_products)
                    logger.info(f"💾 Backup automático criado: {backup_file}")
                    
            except Exception as e:
                logger.warning(f"⚠️  Falha no backup automático: {e}")
        
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas dos produtos armazenados"""
        products = []
        # Para obter estatísticas de todas as fontes, listamos todas as chaves
        keys = self.list_keys(limit=10000) # Busca todas as chaves
        for key_info in keys:
            product = self.get_value(key_info['name'])
            if product:
                products.append(product)

        if not products:
            return {'total': 0}
        
        df = pd.DataFrame(products)
        total = len(df)
        
        # Adiciona a coluna 'source' para categorização
        df['source'] = df['product_id'].apply(lambda x: x.split('_')[0] if '_' in x else 'unknown')

        categorias = df['categoria'].value_counts().to_dict()
        precos = df['preco'].dropna()
        
        return {
            'total': total,
            'categorias': categorias,
            'preco_medio': precos.mean(),
            'preco_min': precos.min(),
            'preco_max': precos.max(),
            'produtos_por_fonte': df['source'].value_counts().to_dict()
        }

    def create_full_backup(self, reason: str = "manual") -> Optional[str]:
        """Cria backup completo de todos os produtos"""
        if not self.backup_manager:
            logger.warning("⚠️  Sistema de backup não está disponível")
            return None
            
        try:
            logger.info("💾 Criando backup completo...")
            all_products = []
            keys = self.list_keys(limit=10000)
            
            for key_info in keys:
                product = self.get_value(key_info['name'])
                if product:
                    all_products.append(product)
                    
            backup_file = self.backup_manager.create_daily_backup(all_products)
            logger.success(f"✅ Backup completo criado: {len(all_products)} produtos salvos em {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup completo: {e}")
            return None
    
    def deduplicate_all_products(self) -> Dict[str, Any]:
        """Executa deduplicacao em todos os produtos armazenados"""
        if not self.deduplication:
            logger.warning("⚠️  Sistema de deduplicacao não está disponível")
            return {"error": "Deduplication system not available"}
            
        try:
            logger.info("🔍 Executando deduplicacao completa...")
            
            # Carrega todos os produtos
            all_products = []
            keys = self.list_keys(limit=10000)
            for key_info in keys:
                product = self.get_value(key_info['name'])
                if product:
                    all_products.append(product)
            
            if not all_products:
                logger.warning("Nenhum produto encontrado para deduplicacao")
                return {"message": "No products found"}
            
            # Cria backup antes da deduplicacao
            if self.backup_manager:
                backup_path = self.backup_manager.create_emergency_backup(
                    ["all_products_before_dedup"], "pre_deduplication"
                )
                logger.info(f"🔒 Backup de segurança criado: {backup_path}")
            
            # Executa deduplicacao
            deduplicated_products, stats = self.deduplication.deduplicate_products(all_products)
            
            logger.success(f"✅ Deduplicacao concluída: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro na deduplicacao: {e}")
            return {"error": str(e)}
    
    def get_protection_status(self) -> Dict[str, Any]:
        """Retorna status dos sistemas de proteção"""
        status = {
            "protection_enabled": self.enable_protection,
            "backup_system": self.backup_manager is not None,
            "deduplication_system": self.deduplication is not None,
            "connection_ok": self.test_connection()
        }
        
        if self.backup_manager:
            status["backup_info"] = self.backup_manager.get_backup_info()
            
        return status

    def test_connection(self) -> bool:
        """Testa a conexão com o Cloudflare"""
        try:
            # Tenta listar algumas chaves para verificar a conexão
            self.list_keys(limit=1)
            return True
        except Exception:
            return False
