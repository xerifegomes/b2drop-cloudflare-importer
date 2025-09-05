# Cloudflare Integration

Integração completa com Cloudflare para gerenciamento de DNS, Workers, R2 e outros serviços.

## 🚀 Instalação

As dependências já estão instaladas:

```bash
# Biblioteca Python
pip install cloudflare

# CLI Wrangler (já instalado globalmente)
npm install -g wrangler
```

## 🔑 Configuração

### Opção 1: API Token (Recomendado)

```bash
export CLOUDFLARE_API_TOKEN="seu_token_aqui"
```

### Opção 2: Email + API Key

```bash
export CLOUDFLARE_EMAIL="seu_email@exemplo.com"
export CLOUDFLARE_API_KEY="sua_chave_aqui"
```

### Obter Credenciais

1. Acesse: https://dash.cloudflare.com/profile/api-tokens
2. Crie um novo token com as permissões necessárias
3. Configure as variáveis de ambiente

## 📋 Scripts Disponíveis

### 1. Teste de Conexão
```bash
python cloudflare_helper.py
```

### 2. Demonstração Completa
```bash
python cloudflare_demo.py
```

### 3. CLI Wrangler
```bash
wrangler --version
wrangler login
wrangler whoami
```

## 🛠️ Funcionalidades

### CloudflareHelper Class

```python
from cloudflare_helper import CloudflareHelper

# Inicializar
cf = CloudflareHelper()

# Testar conexão
cf.test_connection()

# Listar contas
accounts = cf.get_accounts()

# Listar zonas DNS
zones = cf.get_zones()

# Listar registros DNS
records = cf.get_dns_records(zone_id)

# Criar registro DNS
cf.create_dns_record(zone_id, "subdomain", "1.2.3.4", "A")

# Listar Workers
workers = cf.get_workers()

# Listar buckets R2
buckets = cf.get_r2_buckets()
```

## 📊 Exemplos de Uso

### Gerenciar DNS
```python
# Listar todas as zonas
zones = cf.get_zones()
for zone in zones['result']:
    print(f"Zona: {zone['name']}")
    
    # Listar registros da zona
    records = cf.get_dns_records(zone['id'])
    for record in records['result']:
        print(f"  {record['name']} -> {record['content']}")
```

### Criar Registro DNS
```python
# Criar registro A
cf.create_dns_record(
    zone_id="zone_id_aqui",
    name="subdomain.exemplo.com",
    content="1.2.3.4",
    record_type="A",
    ttl=300
)
```

### Gerenciar Workers
```python
# Listar Workers
workers = cf.get_workers()
for worker in workers['result']:
    print(f"Worker: {worker['id']}")
```

## 🔧 Comandos Wrangler

### Autenticação
```bash
wrangler login
```

### Gerenciar Workers
```bash
# Listar Workers
wrangler workers list

# Criar Worker
wrangler init meu-worker

# Deploy Worker
wrangler deploy

# Executar Worker localmente
wrangler dev
```

### Gerenciar R2
```bash
# Listar buckets
wrangler r2 bucket list

# Criar bucket
wrangler r2 bucket create meu-bucket

# Upload arquivo
wrangler r2 object put meu-bucket/arquivo.txt --file=arquivo.txt
```

## 📁 Estrutura de Arquivos

```
importer/
├── cloudflare_helper.py      # Helper principal
├── cloudflare_demo.py        # Demonstração
├── CLOUDFLARE.md            # Esta documentação
└── env.example              # Variáveis de ambiente
```

## 🚨 Troubleshooting

### Erro de Autenticação
- Verifique se as credenciais estão corretas
- Confirme se o token tem as permissões necessárias
- Teste com `wrangler whoami`

### Erro de Permissão
- Verifique se o token tem acesso à conta/zona
- Use tokens com escopo específico

### Erro de Conexão
- Verifique sua conexão com a internet
- Confirme se não há firewall bloqueando

## 📚 Recursos Adicionais

- [Documentação Cloudflare API](https://developers.cloudflare.com/api/)
- [Documentação Wrangler](https://developers.cloudflare.com/workers/wrangler/)
- [Cloudflare Dashboard](https://dash.cloudflare.com/)
- [Exemplos de Workers](https://github.com/cloudflare/worker-examples)
