#!/usr/bin/env python3
"""
Backup Manager - Sistema de Backup e Versionamento para Proteção de Dados
Implementa backup automático e versionamento de produtos antes de sobrescritas
"""

import os
import json
import time
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger
import pandas as pd

class BackupManager:
    """Gerenciador de backup e versionamento de produtos"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Diretórios organizados
        self.daily_backups = self.backup_dir / "daily"
        self.version_backups = self.backup_dir / "versions"
        self.emergency_backups = self.backup_dir / "emergency"
        
        for dir_path in [self.daily_backups, self.version_backups, self.emergency_backups]:
            dir_path.mkdir(exist_ok=True)
        
        logger.info(f"🛡️ Backup Manager inicializado em: {self.backup_dir}")

    def create_emergency_backup(self, source_files: List[str], reason: str = "emergency") -> str:
        """Cria backup de emergência antes de operações críticas"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"emergency_{reason}_{timestamp}"
        backup_path = self.emergency_backups / backup_name
        backup_path.mkdir(exist_ok=True)
        
        logger.warning(f"🚨 Criando backup de emergência: {backup_name}")
        
        backup_info = {
            "timestamp": timestamp,
            "reason": reason,
            "files_backed_up": [],
            "total_size": 0
        }
        
        for file_path in source_files:
            if os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                dest_path = backup_path / file_name
                shutil.copy2(file_path, dest_path)
                
                file_size = os.path.getsize(file_path)
                backup_info["files_backed_up"].append({
                    "original": file_path,
                    "backup": str(dest_path),
                    "size": file_size
                })
                backup_info["total_size"] += file_size
        
        # Salva informações do backup
        info_file = backup_path / "backup_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2, ensure_ascii=False)
        
        logger.success(f"✅ Backup de emergência criado: {backup_path}")
        return str(backup_path)

    def create_daily_backup(self, products_data: List[Dict]) -> str:
        """Cria backup diário dos produtos"""
        today = datetime.now().strftime("%Y-%m-%d")
        backup_file = self.daily_backups / f"products_backup_{today}.json"
        
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "total_products": len(products_data),
            "products": products_data,
            "statistics": self._calculate_backup_stats(products_data)
        }
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📅 Backup diário criado: {backup_file}")
        return str(backup_file)

    def create_version_backup(self, product_id: str, old_data: Dict, new_data: Dict) -> str:
        """Cria backup de versão antes de atualizar produto"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Microsegundos para unicidade
        version_file = self.version_backups / f"{product_id}_{timestamp}.json"
        
        version_data = {
            "product_id": product_id,
            "timestamp": timestamp,
            "old_version": old_data,
            "new_version": new_data,
            "changes": self._detect_changes(old_data, new_data)
        }
        
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"📝 Versão salva para produto {product_id}: {version_file}")
        return str(version_file)

    def _detect_changes(self, old_data: Dict, new_data: Dict) -> List[Dict]:
        """Detecta mudanças entre versões de produtos"""
        changes = []
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            old_value = old_data.get(key)
            new_value = new_data.get(key)
            
            if old_value != new_value:
                changes.append({
                    "field": key,
                    "old_value": old_value,
                    "new_value": new_value,
                    "change_type": self._classify_change(old_value, new_value)
                })
        
        return changes

    def _classify_change(self, old_value, new_value) -> str:
        """Classifica o tipo de mudança"""
        if old_value is None:
            return "added"
        elif new_value is None:
            return "removed"
        elif type(old_value) != type(new_value):
            return "type_changed"
        else:
            return "updated"

    def _calculate_backup_stats(self, products_data: List[Dict]) -> Dict:
        """Calcula estatísticas do backup"""
        if not products_data:
            return {"total": 0}
        
        df = pd.DataFrame(products_data)
        
        stats = {
            "total": len(df),
            "sources": df['source'].value_counts().to_dict() if 'source' in df.columns else {},
            "categories": df['categoria'].value_counts().to_dict() if 'categoria' in df.columns else {},
            "price_range": {
                "min": float(df['preco'].min()) if 'preco' in df.columns else 0,
                "max": float(df['preco'].max()) if 'preco' in df.columns else 0,
                "avg": float(df['preco'].mean()) if 'preco' in df.columns else 0
            }
        }
        
        return stats

    def cleanup_old_backups(self, days_to_keep: int = 7):
        """Remove backups antigos para economizar espaço"""
        cutoff_time = time.time() - (days_to_keep * 24 * 3600)
        cleaned_count = 0
        
        for backup_type in [self.daily_backups, self.version_backups]:
            for backup_file in backup_type.iterdir():
                if backup_file.stat().st_mtime < cutoff_time:
                    if backup_file.is_file():
                        backup_file.unlink()
                        cleaned_count += 1
                    elif backup_file.is_dir():
                        shutil.rmtree(backup_file)
                        cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"🧹 Limpeza de backups: {cleaned_count} arquivos/pastas antigas removidas")

    def restore_from_backup(self, backup_path: str) -> List[Dict]:
        """Restaura produtos de um backup"""
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            logger.error(f"❌ Arquivo de backup não encontrado: {backup_path}")
            return []
        
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            if 'products' in backup_data:
                products = backup_data['products']
                logger.success(f"📦 Backup restaurado: {len(products)} produtos de {backup_path}")
                return products
            else:
                logger.error(f"❌ Formato de backup inválido: {backup_path}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro ao restaurar backup {backup_path}: {e}")
            return []

    def get_backup_info(self) -> Dict:
        """Retorna informações sobre os backups disponíveis"""
        info = {
            "backup_directory": str(self.backup_dir),
            "daily_backups": [],
            "version_backups_count": 0,
            "emergency_backups": [],
            "total_size_mb": 0
        }
        
        # Backups diários
        for backup_file in self.daily_backups.iterdir():
            if backup_file.is_file() and backup_file.suffix == '.json':
                info["daily_backups"].append({
                    "file": backup_file.name,
                    "date": backup_file.stat().st_mtime,
                    "size_mb": backup_file.stat().st_size / (1024*1024)
                })
        
        # Contagem de backups de versão
        info["version_backups_count"] = len(list(self.version_backups.iterdir()))
        
        # Backups de emergência
        for emergency_dir in self.emergency_backups.iterdir():
            if emergency_dir.is_dir():
                info["emergency_backups"].append({
                    "name": emergency_dir.name,
                    "date": emergency_dir.stat().st_mtime,
                    "files_count": len(list(emergency_dir.iterdir()))
                })
        
        # Tamanho total
        info["total_size_mb"] = sum(
            f.stat().st_size for f in self.backup_dir.rglob('*') if f.is_file()
        ) / (1024*1024)
        
        return info