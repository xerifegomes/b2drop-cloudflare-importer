"""
Sistema principal de importação B2Drop
Orquestra todo o processo de scraping, processamento e exportação
"""

import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from .scraper import B2DropScraper
from .data_processor import DataProcessor
from .exporter import DataExporter
from .models import Product, ImportResult
from .config import settings


class B2DropImporter:
    """Sistema principal de importação do catálogo B2Drop"""
    
    def __init__(self, export_format: str = None):
        self.scraper = B2DropScraper()
        self.processor = DataProcessor()
        self.exporter = DataExporter()
        self.export_format = export_format or settings.export_format
        
        # Configuração de logging
        logger.add(
            "logs/b2drop_importer.log",
            rotation="1 day",
            retention="30 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
    
    def import_catalog(self, 
                      export_format: str = None,
                      export_by_category: bool = False,
                      include_summary: bool = True) -> Dict[str, Any]:
        """
        Executa importação completa do catálogo
        
        Args:
            export_format: Formato de exportação (csv, json, excel)
            export_by_category: Se deve exportar por categoria
            include_summary: Se deve incluir resumo na exportação
        
        Returns:
            Dict com resultados da importação
        """
        start_time = time.time()
        logger.info("=== INICIANDO IMPORTAÇÃO B2DROP ===")
        
        try:
            # Etapa 1: Scraping
            logger.info("Etapa 1: Extraindo dados do catálogo...")
            raw_products = self.scraper.scrape_catalog()
            
            if not raw_products:
                logger.error("Nenhum produto extraído do catálogo")
                return self._create_error_result("Nenhum produto encontrado")
            
            logger.info(f"Produtos extraídos: {len(raw_products)}")
            
            # Etapa 2: Processamento
            logger.info("Etapa 2: Processando e validando dados...")
            processed_products = self.processor.process_products(raw_products)
            
            if not processed_products:
                logger.error("Nenhum produto válido após processamento")
                return self._create_error_result("Falha no processamento de dados")
            
            logger.info(f"Produtos processados: {len(processed_products)}")
            
            # Etapa 3: Geração de estatísticas
            logger.info("Etapa 3: Gerando estatísticas...")
            stats = self.processor.generate_stats(processed_products)
            
            # Etapa 4: Criação do resultado
            duration = time.time() - start_time
            import_result = self.processor.create_import_result(processed_products, duration)
            
            # Etapa 5: Exportação
            logger.info("Etapa 4: Exportando dados...")
            export_files = self._export_data(
                processed_products, 
                import_result, 
                export_format or self.export_format,
                export_by_category
            )
            
            # Resultado final
            result = {
                'success': True,
                'import_result': import_result,
                'statistics': stats,
                'export_files': export_files,
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info("=== IMPORTAÇÃO CONCLUÍDA COM SUCESSO ===")
            logger.info(f"Duração total: {duration:.2f} segundos")
            logger.info(f"Produtos importados: {import_result.total_products}")
            logger.info(f"Variações importadas: {import_result.total_variations}")
            logger.info(f"Taxa de sucesso: {import_result.success_rate:.1f}%")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Erro durante importação: {e}")
            return self._create_error_result(str(e), duration)
    
    def _export_data(self, 
                    products: List[Product], 
                    import_result: ImportResult,
                    format: str,
                    export_by_category: bool) -> List[str]:
        """Exporta dados nos formatos especificados"""
        export_files = []
        
        try:
            if format.lower() == 'csv':
                if export_by_category:
                    files = self.exporter.export_products_by_category(products, 'csv')
                    export_files.extend(files)
                else:
                    filepath = self.exporter.export_to_csv(products)
                    export_files.append(filepath)
            
            elif format.lower() == 'json':
                if export_by_category:
                    files = self.exporter.export_products_by_category(products, 'json')
                    export_files.extend(files)
                else:
                    filepath = self.exporter.export_to_json(products, import_result)
                    export_files.append(filepath)
            
            elif format.lower() == 'excel':
                filepath = self.exporter.export_to_excel(products, import_result)
                export_files.append(filepath)
            
            elif format.lower() == 'all':
                # Exporta em todos os formatos
                csv_file = self.exporter.export_to_csv(products)
                json_file = self.exporter.export_to_json(products, import_result)
                excel_file = self.exporter.export_to_excel(products, import_result)
                
                export_files.extend([csv_file, json_file, excel_file])
            
            else:
                logger.warning(f"Formato {format} não reconhecido, usando CSV")
                filepath = self.exporter.export_to_csv(products)
                export_files.append(filepath)
            
            logger.info(f"Arquivos exportados: {len(export_files)}")
            for file in export_files:
                logger.info(f"  - {file}")
            
        except Exception as e:
            logger.error(f"Erro na exportação: {e}")
            raise
        
        return export_files
    
    def _create_error_result(self, error_message: str, duration: float = 0) -> Dict[str, Any]:
        """Cria resultado de erro"""
        return {
            'success': False,
            'error': error_message,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'import_result': None,
            'statistics': {},
            'export_files': []
        }
    
    def get_catalog_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do catálogo sem fazer importação completa"""
        try:
            logger.info("Obtendo estatísticas do catálogo...")
            raw_products = self.scraper.scrape_catalog()
            
            if not raw_products:
                return {'error': 'Nenhum produto encontrado'}
            
            processed_products = self.processor.process_products(raw_products)
            stats = self.processor.generate_stats(processed_products)
            
            return {
                'success': True,
                'statistics': stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {'error': str(e)}
    
    def validate_connection(self) -> bool:
        """Valida conexão com o site B2Drop"""
        try:
            logger.info("Validando conexão com B2Drop...")
            response = self.scraper._make_request(self.scraper.catalog_url)
            
            if response and response.status_code == 200:
                logger.info("Conexão validada com sucesso")
                return True
            else:
                logger.error("Falha na validação da conexão")
                return False
                
        except Exception as e:
            logger.error(f"Erro na validação: {e}")
            return False
