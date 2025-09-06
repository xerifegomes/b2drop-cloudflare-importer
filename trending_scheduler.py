#!/usr/bin/env python3
"""
Trending Scheduler - Sistema de agendamento inteligente
Executa scraping a cada 2 horas baseado em leads e tendências
"""

import os
import sys
import time
import schedule
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from dotenv import load_dotenv

# Adiciona path
sys.path.append(os.path.dirname(__file__))

from top_products_aggregator import TopProductsAggregator
from cloudflare_storage_fixed import CloudflareStorage

# Carrega variáveis
load_dotenv('.env.apis')


class TrendingScheduler:
    """Scheduler inteligente para coleta de produtos trending"""
    
    def __init__(self):
        self.aggregator = TopProductsAggregator()
        self.storage = CloudflareStorage()
        
        # Configurações de agendamento
        self.interval_hours = 2  # A cada 2 horas
        self.max_products_per_run = 150  # Limite por execução
        self.running = False
        
        # Sistema de leads/tendências dinâmicas
        self.trending_keywords = {
            # Eletrônicos trending
            "tech": [
                "iphone 16", "samsung galaxy s25", "airpods pro", 
                "macbook air m3", "ipad pro", "nintendo switch",
                "ps5", "xbox series x", "steam deck"
            ],
            
            # Casa & Eletrodomésticos  
            "home": [
                "air fryer", "robot aspirador", "smart tv 55", 
                "geladeira inverter", "fogão 5 bocas", "microondas",
                "cafeteira nespresso", "liquidificador vitamina"
            ],
            
            # Moda & Beleza
            "fashion": [
                "tênis nike air", "bolsa coach", "perfume importado",
                "óculos ray ban", "relógio apple watch", "maquiagem mac"
            ],
            
            # Saúde & Fitness
            "health": [
                "whey protein", "creatina", "vitamina d3",
                "esteira elétrica", "bike ergométrica", "suplemento"
            ],
            
            # Trending atual (sazonal)
            "seasonal": [
                "presente natal", "black friday", "volta às aulas",
                "dia das mães", "festa junina", "carnaval 2025"
            ]
        }
        
        # Proxies rotativos (será implementado)
        self.proxy_rotation = {
            "enabled": False,  # Habilitar quando necessário
            "proxies": [],
            "current_index": 0
        }
        
        # Métricas de performance
        self.performance_stats = {
            "total_runs": 0,
            "successful_runs": 0,
            "products_collected": 0,
            "last_run": None,
            "average_products_per_run": 0,
            "best_categories": {}
        }
        
        logger.info("📅 Trending Scheduler inicializado")
        logger.info(f"⏰ Intervalo: {self.interval_hours} horas")
        logger.info(f"🎯 Keywords trending: {sum(len(kw) for kw in self.trending_keywords.values())}")
    
    def get_dynamic_categories(self) -> List[str]:
        """Retorna categorias baseadas em tendências atuais"""
        try:
            current_hour = datetime.now().hour
            day_of_week = datetime.now().weekday()  # 0=Monday
            
            # Algoritmo inteligente baseado em horário e dia
            trending_categories = []
            
            # Manhã (6-12h): Eletrônicos e Casa
            if 6 <= current_hour <= 12:
                trending_categories.extend(self.trending_keywords["tech"][:4])
                trending_categories.extend(self.trending_keywords["home"][:3])
            
            # Tarde (12-18h): Moda e Saúde  
            elif 12 <= current_hour <= 18:
                trending_categories.extend(self.trending_keywords["fashion"][:3])
                trending_categories.extend(self.trending_keywords["health"][:4])
            
            # Noite (18-24h): Mix geral + Sazonal
            else:
                trending_categories.extend(self.trending_keywords["tech"][:2])
                trending_categories.extend(self.trending_keywords["seasonal"][:3])
                trending_categories.extend(self.trending_keywords["home"][:2])
            
            # Fim de semana: Foco em lazer
            if day_of_week >= 5:  # Sábado e Domingo
                trending_categories.extend(["console games", "smart tv", "bicicleta"])
            
            # Remove duplicatas e limita
            unique_categories = list(dict.fromkeys(trending_categories))[:15]
            
            logger.info(f"🎯 Categorias dinâmicas selecionadas: {len(unique_categories)}")
            return unique_categories
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar categorias dinâmicas: {e}")
            return ["smartphone", "notebook", "fone de ouvido"]  # Fallback
    
    def run_trending_collection(self) -> Dict:
        """Executa uma coleta de produtos trending"""
        try:
            logger.info("🚀 Iniciando coleta agendada de produtos trending...")
            
            start_time = time.time()
            self.performance_stats["total_runs"] += 1
            
            # Substitui categorias fixas por dinâmicas
            dynamic_categories = self.get_dynamic_categories()
            self.aggregator.top_physical_categories = dynamic_categories
            
            # Executa análise com categorias dinâmicas
            results = self.aggregator.run_full_analysis(
                save_results=True,
                store_cloudflare=True
            )
            
            if results and results.get('products'):
                products_count = len(results['products'])
                storage_result = results.get('storage_result', {})
                
                # Atualiza estatísticas
                self.performance_stats["successful_runs"] += 1
                self.performance_stats["products_collected"] += products_count
                self.performance_stats["last_run"] = datetime.now().isoformat()
                self.performance_stats["average_products_per_run"] = (
                    self.performance_stats["products_collected"] / 
                    self.performance_stats["successful_runs"]
                )
                
                # Análise de performance por categoria
                self._update_category_performance(results['products'])
                
                execution_time = time.time() - start_time
                
                logger.success(f"✅ Coleta concluída em {execution_time:.1f}s")
                logger.success(f"📦 Produtos coletados: {products_count}")
                logger.success(f"☁️ Cloudflare: {storage_result.get('success', 0)} armazenados")
                logger.success(f"🖼️ Imagens: {storage_result.get('images_uploaded', 0)} uploadadas")
                
                return {
                    "success": True,
                    "products_count": products_count,
                    "execution_time": execution_time,
                    "storage_result": storage_result
                }
            
            else:
                logger.error("❌ Falha na coleta de produtos")
                return {"success": False, "error": "No products collected"}
                
        except Exception as e:
            logger.error(f"❌ Erro na coleta agendada: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_category_performance(self, products: List[Dict]):
        """Atualiza métricas de performance por categoria"""
        try:
            category_counts = {}
            
            for product in products:
                category = product.get('category_searched', 'unknown')
                score = product.get('trending_score', 0)
                
                if category not in category_counts:
                    category_counts[category] = {"count": 0, "total_score": 0, "avg_score": 0}
                
                category_counts[category]["count"] += 1
                category_counts[category]["total_score"] += score
                category_counts[category]["avg_score"] = (
                    category_counts[category]["total_score"] / 
                    category_counts[category]["count"]
                )
            
            # Atualiza estatísticas globais
            for category, stats in category_counts.items():
                if category not in self.performance_stats["best_categories"]:
                    self.performance_stats["best_categories"][category] = {
                        "total_products": 0,
                        "avg_score": 0,
                        "success_rate": 0
                    }
                
                current = self.performance_stats["best_categories"][category]
                current["total_products"] += stats["count"]
                current["avg_score"] = (current["avg_score"] + stats["avg_score"]) / 2
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar performance: {e}")
    
    def start_scheduler(self):
        """Inicia o agendamento automático"""
        try:
            logger.info(f"📅 Iniciando scheduler - execução a cada {self.interval_hours}h")
            
            # Agenda execução a cada N horas
            schedule.every(self.interval_hours).hours.do(self.run_trending_collection)
            
            # Execução inicial imediata (opcional)
            # logger.info("🚀 Executando primeira coleta imediata...")
            # self.run_trending_collection()
            
            self.running = True
            
            # Loop principal do scheduler
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Verifica a cada minuto
                
        except KeyboardInterrupt:
            logger.info("⏹️ Scheduler interrompido pelo usuário")
            self.stop_scheduler()
        except Exception as e:
            logger.error(f"❌ Erro no scheduler: {e}")
            self.stop_scheduler()
    
    def stop_scheduler(self):
        """Para o scheduler"""
        self.running = False
        schedule.clear()
        logger.info("⏹️ Scheduler parado")
    
    def get_performance_report(self) -> Dict:
        """Gera relatório de performance do scheduler"""
        try:
            stats = self.performance_stats.copy()
            
            # Top 5 categorias por performance
            best_categories = sorted(
                stats["best_categories"].items(),
                key=lambda x: x[1]["avg_score"],
                reverse=True
            )[:5]
            
            stats["top_categories"] = best_categories
            
            # Tempo desde última execução
            if stats["last_run"]:
                last_run = datetime.fromisoformat(stats["last_run"])
                time_since = datetime.now() - last_run
                stats["time_since_last_run"] = str(time_since)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro no relatório: {e}")
            return {}
    
    def run_once(self):
        """Executa uma coleta única (para testes)"""
        logger.info("🧪 Executando coleta única...")
        return self.run_trending_collection()
    
    def set_interval(self, hours: int):
        """Altera intervalo de execução"""
        if 1 <= hours <= 24:
            self.interval_hours = hours
            logger.info(f"⏰ Intervalo alterado para {hours} horas")
            
            # Reagenda se estiver rodando
            if self.running:
                schedule.clear()
                schedule.every(self.interval_hours).hours.do(self.run_trending_collection)
        else:
            logger.error("❌ Intervalo deve estar entre 1 e 24 horas")


def main():
    """Função principal CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Trending Scheduler")
    parser.add_argument('--mode', choices=['start', 'once', 'stats'], default='once',
                       help='Modo de execução')
    parser.add_argument('--interval', type=int, default=2,
                       help='Intervalo em horas (1-24)')
    
    args = parser.parse_args()
    
    scheduler = TrendingScheduler()
    
    if args.interval != 2:
        scheduler.set_interval(args.interval)
    
    if args.mode == 'start':
        logger.info("🚀 Iniciando scheduler em modo contínuo...")
        scheduler.start_scheduler()
        
    elif args.mode == 'once':
        logger.info("🧪 Executando coleta única...")
        result = scheduler.run_once()
        
        if result.get('success'):
            print(f"✅ Sucesso: {result['products_count']} produtos coletados")
        else:
            print(f"❌ Falha: {result.get('error', 'Erro desconhecido')}")
            
    elif args.mode == 'stats':
        stats = scheduler.get_performance_report()
        
        print("\n" + "="*50)
        print("📊 RELATÓRIO DE PERFORMANCE")
        print("="*50)
        print(f"🔄 Total de execuções: {stats['total_runs']}")
        print(f"✅ Execuções bem-sucedidas: {stats['successful_runs']}")
        print(f"📦 Produtos coletados: {stats['products_collected']}")
        print(f"📈 Média por execução: {stats['average_products_per_run']:.1f}")
        
        if stats.get('top_categories'):
            print(f"\n🏆 TOP 5 CATEGORIAS:")
            for i, (cat, data) in enumerate(stats['top_categories'], 1):
                print(f"  {i}. {cat}: {data['total_products']} produtos (Score: {data['avg_score']:.1f})")


if __name__ == "__main__":
    main()