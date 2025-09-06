#!/usr/bin/env python3
"""
Scrapy Manager - Controle avançado do scraping B2Drop
Integra Scrapy com nossa arquitetura existente
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path

# Adiciona paths necessários
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from loguru import logger
from cloudflare_storage_fixed import CloudflareStorage


class ScrapyManager:
    """Gerenciador principal do Scrapy para B2Drop"""
    
    def __init__(self):
        self.project_dir = project_root / "b2drop_scraper"
        self.logs_dir = project_root / "logs"
        self.storage = None
        
        # Cria diretórios necessários
        self.logs_dir.mkdir(exist_ok=True)
        (self.project_dir / "logs").mkdir(exist_ok=True)
        
        logger.info("🚀 Scrapy Manager inicializado")
    
    def check_environment(self):
        """Verifica se ambiente está configurado corretamente"""
        logger.info("🔍 Verificando ambiente...")
        
        # Verifica variáveis de ambiente
        required_vars = [
            'CLOUDFLARE_API_TOKEN',
            'CLOUDFLARE_ACCOUNT_ID', 
            'CLOUDFLARE_KV_NAMESPACE_ID',
            'CLOUDFLARE_R2_BUCKET_NAME',
            'CLOUDFLARE_R2_PUBLIC_DOMAIN'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Variáveis de ambiente faltando: {missing_vars}")
            return False
        
        # Testa conexão Cloudflare
        try:
            self.storage = CloudflareStorage()
            if not self.storage.init_r2_bucket():
                logger.error("❌ Falha ao conectar com Cloudflare")
                return False
        except Exception as e:
            logger.error(f"❌ Erro na conexão Cloudflare: {e}")
            return False
        
        # Verifica se projeto Scrapy existe
        if not (self.project_dir / "scrapy.cfg").exists():
            logger.error(f"❌ Projeto Scrapy não encontrado em {self.project_dir}")
            return False
        
        logger.info("✅ Ambiente verificado com sucesso")
        return True
    
    def run_spider(self, spider_name="b2drop", **kwargs):
        """Executa spider Scrapy"""
        if not self.check_environment():
            return False
        
        logger.info(f"🕷️ Iniciando spider: {spider_name}")
        
        # Prepara comando Scrapy
        cmd = [
            "scrapy", "crawl", spider_name,
            "-L", "INFO",
            f"-s", f"LOG_FILE={self.logs_dir}/scrapy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ]
        
        # Adiciona parâmetros extras
        for key, value in kwargs.items():
            cmd.extend(["-a", f"{key}={value}"])
        
        # Executa comando
        try:
            logger.info(f"📝 Executando: {' '.join(cmd)}")
            
            process = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=False,
                text=True,
                timeout=3600  # Timeout de 1 hora
            )
            
            if process.returncode == 0:
                logger.info("✅ Spider executado com sucesso")
                return True
            else:
                logger.error(f"❌ Spider falhou com código: {process.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Spider excedeu tempo limite (1 hora)")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao executar spider: {e}")
            return False
    
    def get_statistics(self):
        """Obtém estatísticas dos produtos armazenados"""
        if not self.storage:
            try:
                self.storage = CloudflareStorage()
                self.storage.init_r2_bucket()
            except:
                logger.error("❌ Não foi possível conectar ao Cloudflare")
                return None
        
        logger.info("📊 Coletando estatísticas...")
        stats = self.storage.get_statistics()
        
        if stats and stats.get('total', 0) > 0:
            logger.info("="*50)
            logger.info("📈 ESTATÍSTICAS ATUAIS")
            logger.info("="*50)
            logger.info(f"📦 Total de produtos: {stats['total']}")
            logger.info(f"💰 Preço médio: R$ {stats.get('preco_medio', 0):.2f}")
            logger.info(f"💰 Preço mínimo: R$ {stats.get('preco_min', 0):.2f}")
            logger.info(f"💰 Preço máximo: R$ {stats.get('preco_max', 0):.2f}")
            
            if stats.get('categorias'):
                logger.info("🏷️ Produtos por categoria:")
                for cat, count in stats['categorias'].items():
                    logger.info(f"   • {cat}: {count}")
            
            logger.info("="*50)
        else:
            logger.warning("⚠️ Nenhuma estatística disponível")
        
        return stats
    
    def compare_with_existing(self):
        """Compara dados atuais com sistema legado"""
        logger.info("🔍 Comparando com dados existentes...")
        
        # Executa listagem do sistema atual
        try:
            result = subprocess.run([
                "python", "import_to_cloudflare.py", "stats"
            ], capture_output=True, text=True, cwd=project_root)
            
            if result.returncode == 0:
                logger.info("📊 Dados do sistema atual:")
                for line in result.stdout.split('\n'):
                    if 'Total de produtos:' in line or 'Preço' in line:
                        logger.info(f"   {line.strip()}")
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível acessar sistema atual: {e}")
    
    def scheduled_run(self, interval_minutes=60):
        """Executa spider em intervalos regulares"""
        logger.info(f"⏰ Iniciando execução agendada (a cada {interval_minutes} minutos)")
        
        while True:
            try:
                logger.info("🔄 Iniciando execução agendada...")
                
                success = self.run_spider()
                if success:
                    self.get_statistics()
                    self.compare_with_existing()
                
                logger.info(f"😴 Aguardando {interval_minutes} minutos...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("⏹️ Execução agendada interrompida pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro na execução agendada: {e}")
                logger.info(f"🔄 Tentando novamente em {interval_minutes} minutos...")
                time.sleep(interval_minutes * 60)


def main():
    """Função principal CLI"""
    parser = argparse.ArgumentParser(description="Scrapy Manager para B2Drop")
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # Comando: run
    run_parser = subparsers.add_parser('run', help='Executa spider uma vez')
    run_parser.add_argument('--spider', default='b2drop', help='Nome do spider')
    
    # Comando: schedule
    schedule_parser = subparsers.add_parser('schedule', help='Executa spider em intervalos')
    schedule_parser.add_argument('--interval', type=int, default=60, help='Intervalo em minutos')
    
    # Comando: stats
    stats_parser = subparsers.add_parser('stats', help='Mostra estatísticas')
    
    # Comando: check
    check_parser = subparsers.add_parser('check', help='Verifica ambiente')
    
    # Comando: compare
    compare_parser = subparsers.add_parser('compare', help='Compara com dados existentes')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ScrapyManager()
    
    if args.command == 'run':
        manager.run_spider(args.spider)
    elif args.command == 'schedule':
        manager.scheduled_run(args.interval)
    elif args.command == 'stats':
        manager.get_statistics()
    elif args.command == 'check':
        success = manager.check_environment()
        sys.exit(0 if success else 1)
    elif args.command == 'compare':
        manager.compare_with_existing()


if __name__ == "__main__":
    main()