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

# Adiciona o diretório src ao path para poder importar o config
sys.path.append(str(Path(__file__).parent.parent / "src"))
from src.config import settings

class CloudflareStorage:
    """Classe unificada para gerenciar armazenamento no Cloudflare KV e R2."""
    
    def __init__(self):
        """Inicializa o cliente de armazenamento."""
        self.api_token = settings.cloudflare_api_token
        self.account_id = settings.cloudflare_account_id
        self.kv_namespace_id = settings.cloudflare_kv_namespace_id
        self.r2_bucket_name = settings.cloudflare_r2_bucket_name
        self.r2_public_url = f"https://{os.getenv('CLOUDFLARE_R2_PUBLIC_DOMAIN')}" # Ex: pub-xxxxxxxx.r2.dev

        if not all([self.api_token, self.account_id, self.kv_namespace_id, self.r2_bucket_name, self.r2_public_url]):
            raise ValueError("Variáveis de ambiente do Cloudflare não estão configuradas: TOKEN, ACCOUNT_ID, KV_ID, R2_BUCKET, R2_DOMAIN")

        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        
        logger.info("🚀 Cloudflare Storage inicializado")
        logger.info(f"🗃️ KV Namespace ID: {self.kv_namespace_id}")
        logger.info(f"🪣 R2 Bucket Name: {self.r2_bucket_name}")

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
            logger.info("🔔 Lembrete: Habilite o acesso público ao bucket no painel Cloudflare para que as imagens sejam visíveis.")
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
                # A API exige minimum 10, máximo 1000 por página
                page_limit = min(max(limit - len(all_keys), 10), 1000)
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

    # --- Métodos de Produtos ---

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Recupera um produto do KV"""
        try:
            url = f"{self.base_url}/storage/kv/namespaces/{self.kv_namespace_id}/values/product:{product_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"❌ Erro ao recuperar produto: {e}")
            return None

    def store_product(self, product_data: Dict[str, Any]) -> bool:
        """Armazena um produto no KV"""
        try:
            product_id = product_data.get('product_id')
            if not product_id:
                logger.error("❌ Product ID não fornecido")
                return False
            
            key = f"product:{product_id}"
            url = f"{self.base_url}/storage/kv/namespaces/{self.kv_namespace_id}/values/{key}"
            response = requests.put(
                url, 
                headers={**self.headers, 'Content-Type': 'application/json'}, 
                data=json.dumps(product_data).encode('utf-8')
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao armazenar produto: {e}")
            return False

    def list_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Lista produtos armazenados"""
        try:
            # Lista todas as chaves do KV (API exige min 10)
            api_limit = max(limit, 10)
            keys_list = self.list_keys(prefix="", limit=api_limit)
            
            if not keys_list:
                logger.warning("❌ Nenhuma chave encontrada no KV")
                return []
            
            logger.info(f"✅ Listagem de chaves OK: {len(keys_list)} chaves encontradas")
            
            products = []
            # Recupera dados de cada chave e verifica se é um produto
            for key_info in keys_list[:limit]:
                key = key_info['name']
                # Tenta recuperar o valor e verifica se tem estrutura de produto
                product_data = self.get_value(key)
                if product_data and isinstance(product_data, dict) and 'produto' in product_data:
                    products.append(product_data)
                    # Para limitar exatamente ao número solicitado
                    if len(products) >= limit:
                        break
            
            logger.info(f"✅ Produtos recuperados: {len(products)}")
            return products
                
        except Exception as e:
            logger.error(f"❌ Erro ao listar produtos: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas dos produtos armazenados"""
        try:
            products = self.list_products(limit=100)
            
            if not products:
                return {'total': 0, 'categorias': {}, 'preco_medio': 0, 'preco_min': 0, 'preco_max': 0}
            
            # Calcula estatísticas
            total = len(products)
            categorias = {}
            precos = []
            
            for product in products:
                # Categorias
                categoria = product.get('categoria', 'Outros')
                categorias[categoria] = categorias.get(categoria, 0) + 1
                
                # Preços
                preco = product.get('preco', 0)
                try:
                    preco = float(preco) if preco else 0
                    if preco > 0:
                        precos.append(preco)
                except (ValueError, TypeError):
                    pass
            
            preco_medio = sum(precos) / len(precos) if precos else 0
            preco_min = min(precos) if precos else 0
            preco_max = max(precos) if precos else 0
            
            return {
                'total': total,
                'categorias': categorias,
                'preco_medio': preco_medio,
                'preco_min': preco_min,
                'preco_max': preco_max
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular estatísticas: {e}")
            return {'total': 0, 'categorias': {}, 'preco_medio': 0, 'preco_min': 0, 'preco_max': 0}

    def store_products_batch(self, products_df: pd.DataFrame) -> Dict[str, Any]:
        """Armazena lote de produtos no Cloudflare"""
        logger.info(f"📦 Iniciando armazenamento de {len(products_df)} produtos")
        
        results = {
            'total_products': len(products_df),
            'successful_uploads': 0,
            'failed_uploads': 0,
            'r2_urls': [],
            'errors': []
        }
        
        for index, row in products_df.iterrows():
            try:
                # Gera um ID único para o produto
                timestamp = int(time.time())
                product_id = f"b2drop_{index}_{timestamp}"
                
                # Prepara dados do produto
                product_data = {
                    'product_id': product_id,
                    'produto': str(row.get('produto', '')),
                    'descricao': str(row.get('descricao', '')),
                    'preco': row.get('preco', 0),
                    'categoria': str(row.get('categoria', '')),
                    'cor': str(row.get('cor', '')),
                    'tamanho': str(row.get('tamanho', '')),
                    'imagem_original': str(row.get('imagem', '')),
                    'imagem_r2': None,
                    'created_at': pd.Timestamp.now().isoformat()
                }
                
                # Upload da imagem para R2 se disponível
                if row.get('imagem'):
                    r2_url = self.upload_image(row['imagem'], product_data['produto'])
                    if r2_url:
                        product_data['imagem_r2'] = r2_url
                        results['r2_urls'].append(r2_url)
                
                # Armazena produto no KV
                if self.store_product(product_data):
                    results['successful_uploads'] += 1
                    logger.debug(f"✅ Produto {product_id} armazenado com sucesso")
                else:
                    results['failed_uploads'] += 1
                    results['errors'].append(f"Falha ao armazenar {product_id}")
                
            except Exception as e:
                results['failed_uploads'] += 1
                results['errors'].append(f"Erro no produto {index}: {str(e)}")
                logger.error(f"❌ Erro no produto {index}: {e}")
        
        logger.info(f"✅ Armazenamento concluído: {results['successful_uploads']} sucessos, {results['failed_uploads']} falhas")
        return results