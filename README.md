# B2Drop Cloudflare Importer

Sistema robusto para importar produtos do B2Drop e armazenar no Cloudflare KV + R2.

## 🚀 Funcionalidades

- ✅ **Import completo** do catálogo B2Drop (294 produtos únicos)
- ✅ **Armazenamento otimizado** no Cloudflare KV + R2
- ✅ **Upload de imagens** para R2 com URLs otimizadas
- ✅ **Listagem e estatísticas** de produtos armazenados
- ✅ **Estrutura modular** e escalável
- ✅ **Tratamento de erros** robusto

## 📊 Status Atual

- **294 produtos únicos** armazenados com sucesso
- **8 categorias** mapeadas (Eletrônicos, Pet Shop, Casa e Organização, etc.)
- **Preços de R$ 3,00 até R$ 380,00**
- **Imagens otimizadas** no Cloudflare R2
- **Sistema em produção** estável

## 🛠️ Instalação

### Pré-requisitos

- Python 3.9+
- Conta Cloudflare com API Token
- KV Namespace e R2 Bucket configurados

### Setup

1. **Clone o repositório:**
```bash
git clone <repository_url>
cd importer
```

2. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

3. **Configure as variáveis de ambiente:**
```bash
cp .env.example .env
# Edite o .env com suas credenciais
```

## ⚙️ Configuração

Configure o arquivo `.env` com suas credenciais:

```env
CLOUDFLARE_API_TOKEN=sua_api_token_aqui
CLOUDFLARE_ACCOUNT_ID=seu_account_id_aqui
CLOUDFLARE_KV_NAMESPACE_ID=seu_kv_namespace_id_aqui
CLOUDFLARE_R2_BUCKET_NAME=seu_bucket_r2_aqui
CLOUDFLARE_R2_PUBLIC_DOMAIN=seu_dominio.r2.dev
```

## 🎯 Uso

### Comandos Principais

**Importar produtos do B2Drop:**
```bash
python import_to_cloudflare.py import
```

**Listar produtos armazenados:**
```bash
python import_to_cloudflare.py list --limit 10
```

**Ver estatísticas:**
```bash
python import_to_cloudflare.py stats
```

### Exemplos de Saída

**Listagem:**
```
1. Fone De Ouvido On-ear Pei-hs01 Bege (Preço: R$ 73.0)
   - Imagem Original: https://app.sistemab2drop.com.br/uploads/...
   - Imagem R2: https://pub-xxx.r2.dev/images/...
```

**Estatísticas:**
```
• Total de produtos: 294
• Preço médio: R$ 47.50
• Preço mínimo: R$ 3.00
• Preço máximo: R$ 380.00
• Produtos por Categoria:
  - Eletrônicos: 19
  - Outros: 45
  - Pet Shop: 11
```

## 📁 Estrutura do Projeto

```
importer/
├── src/                          # Módulos principais
│   ├── __init__.py
│   ├── config.py                 # Configurações
│   ├── scraper.py                # Web scraping B2Drop
│   ├── importer.py               # Lógica de importação
│   ├── data_processor.py         # Processamento de dados
│   ├── exporter.py               # Exportação de dados
│   └── models.py                 # Modelos de dados
├── cloudflare_storage_fixed.py   # Cliente Cloudflare
├── import_to_cloudflare.py       # Script principal
├── requirements.txt              # Dependências
├── .env.example                  # Template de configuração
└── README.md                     # Documentação
```

## 🔧 Arquitetura

### Componentes Principais

1. **B2DropImporter** - Extrai dados do B2Drop
2. **CloudflareStorage** - Interface com KV + R2
3. **DataProcessor** - Processa e valida dados
4. **ScriptCLI** - Interface de linha de comando

### Fluxo de Dados

```
B2Drop → Scraper → Processor → Cloudflare KV + R2
```

## 🚦 Tratamento de Erros

- ✅ **Retry automático** em falhas de rede
- ✅ **Validação de dados** antes do armazenamento
- ✅ **Logs detalhados** com níveis INFO/ERROR/DEBUG
- ✅ **Fallback** para operações críticas

## 🔒 Segurança

- ✅ **Variáveis de ambiente** para credenciais
- ✅ **Validação de entrada** em todos os dados
- ✅ **Rate limiting** nas requisições
- ✅ **Sanitização** de nomes de arquivos

## 📈 Performance

- **294 produtos** processados em ~2 minutos
- **Upload paralelo** de imagens otimizado
- **Cache inteligente** para evitar reprocessamento
- **Paginação** para grandes datasets

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Add nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

## 🆘 Suporte

Para suporte ou dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação do Cloudflare KV/R2
- Verifique os logs de aplicação

---

**Status:** ✅ Produção | **Versão:** 1.0.0 | **Última atualização:** 2025-09-05