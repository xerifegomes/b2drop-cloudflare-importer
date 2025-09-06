# Scrapy settings for b2drop_scraper project
import os

BOT_NAME = "b2drop_scraper"

SPIDER_MODULES = ["b2drop_scraper.spiders"]
NEWSPIDER_MODULE = "b2drop_scraper.spiders"

# Configurações de Rate Limiting e Performance
ROBOTSTXT_OBEY = False  # B2Drop não tem robots.txt relevante
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = 0.5
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# User Agent customizado
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Headers personalizados
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Configurações de Cookies e Sessão
COOKIES_ENABLED = True
COOKIES_DEBUG = False

# Auto-throttle para ajuste automático de velocidade
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Cache HTTP para desenvolvimento
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [404, 500, 502, 503, 504]

# Retry middleware
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Pipeline para processar itens
ITEM_PIPELINES = {
    'b2drop_scraper.pipelines.ValidationPipeline': 200,
    'b2drop_scraper.pipelines.DuplicationFilterPipeline': 300,
    'b2drop_scraper.pipelines.CloudflarePipeline': 400,
}

# Extensions úteis
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
    'scrapy.extensions.memusage.MemoryUsage': 500,
}

# Configurações de logging
LOG_LEVEL = os.getenv('SCRAPY_LOG_LEVEL', 'INFO')
LOG_FILE = 'logs/scrapy.log'

# Configurações do Cloudflare (usando nossas variáveis de ambiente)
CLOUDFLARE_API_TOKEN = os.getenv('CLOUDFLARE_API_TOKEN')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')
CLOUDFLARE_KV_NAMESPACE_ID = os.getenv('CLOUDFLARE_KV_NAMESPACE_ID')
CLOUDFLARE_R2_BUCKET_NAME = os.getenv('CLOUDFLARE_R2_BUCKET_NAME')
CLOUDFLARE_R2_PUBLIC_DOMAIN = os.getenv('CLOUDFLARE_R2_PUBLIC_DOMAIN')

# Configurações específicas do B2Drop
B2DROP_BASE_URL = "https://app.sistemab2drop.com.br"
B2DROP_LOGIN_URL = f"{B2DROP_BASE_URL}/login"
B2DROP_CATALOG_URL = f"{B2DROP_BASE_URL}/products"

# Feed export encoding
FEED_EXPORT_ENCODING = "utf-8"

# Desabilitar telnet para produção
TELNETCONSOLE_ENABLED = False