"""
Configurações do B2Drop Importer
Centraliza todas as configurações do sistema
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()


class Settings(BaseSettings):
    """Configurações da aplicação"""
    
    # URLs
    b2drop_base_url: str = Field(
        default="https://app.sistemab2drop.com.br",
        env="B2DROP_BASE_URL"
    )
    b2drop_catalog_url: str = Field(
        default="https://app.sistemab2drop.com.br/public-catalog",
        env="B2DROP_CATALOG_URL"
    )
    
    # Configurações de Scraping
    request_delay: float = Field(default=1.0, env="REQUEST_DELAY")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    timeout: int = Field(default=30, env="TIMEOUT")
    
    # Configurações de Exportação
    export_format: str = Field(default="csv", env="EXPORT_FORMAT")
    export_dir: str = Field(default="./exports", env="EXPORT_DIR")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Headers
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        env="USER_AGENT"
    )

    # Configurações do Cloudflare
    cloudflare_api_token: Optional[str] = Field(default=None, env="CLOUDFLARE_API_TOKEN")
    cloudflare_account_id: Optional[str] = Field(default=None, env="CLOUDFLARE_ACCOUNT_ID")
    cloudflare_kv_namespace_id: Optional[str] = Field(default=None, env="CLOUDFLARE_KV_NAMESPACE_ID")
    cloudflare_r2_bucket_name: Optional[str] = Field(default="b2drop-products-images", env="CLOUDFLARE_R2_BUCKET_NAME")
    cloudflare_r2_public_domain: Optional[str] = Field(default=None, env="CLOUDFLARE_R2_PUBLIC_DOMAIN")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instância global das configurações
settings = Settings()
