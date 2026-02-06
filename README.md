# 📧 ABAplay Email Automation

Sistema de automação para envio de emails comerciais para clínicas de terapia ABA, com processamento inteligente via IA (GPT-5 mini).

## 🚀 Funcionalidades

### Core
- ✅ Processamento de leads via JSON
- ✅ Sistema de scoring para priorização (0-100)
- ✅ Validação de emails (sintaxe + MX lookup)
- ✅ Delays inteligentes com distribuição gaussiana
- ✅ Respeita horário comercial (9h-18h dias úteis)
- ✅ Limite diário configurável (default: 10/dia)
- ✅ Blacklist para opt-out
- ✅ Relatórios PDF automáticos

### Inteligência Artificial (GPT-5 mini)
- 🧠 Análise contextual de leads via LLM
- 🧠 Geração de emails personalizados por lead
- 🧠 Insights estratégicos para cada contato
- 🧠 Scoring inteligente baseado em potencial de conversão

### Anti-Spam & Proteção
- 🛡️ Verificação de duplicatas (180 dias)
- 🛡️ Aprovação manual para reenvios
- 🛡️ Headers List-Unsubscribe em todos os emails
- 🛡️ Warmup gradual de domínio

## 📋 Requisitos

- Python 3.9+
- Conta Resend com domínio verificado
- Email Zoho configurado no Resend
- API Key OpenAI (para funcionalidades de IA)

## 🔧 Instalação

1. Entre no diretório:
```bash
cd email_abaplay_resend
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure o arquivo `.env`:
```bash
cp .env.example .env
# Edite e preencha:
# - RESEND_API_KEY (sua API do Resend)
# - SENDER_EMAIL (seu email Zoho)
# - OPENAI_API_KEY (sua API da OpenAI)
```

## ▶️ Executando

1. Ative o ambiente virtual:
```bash
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

2. Inicie a aplicação:
```bash
streamlit run app/main.py
```

3. Acesse: http://localhost:8501

## 📖 Como Usar

### 1. Cole o JSON de Leads

Na aba "Nova Campanha", cole o JSON no formato:

```json
{
  "regiao_buscada": "Santos SP",
  "leads": [
    {
      "nome_clinica": "Clínica Exemplo",
      "cidade_uf": "Santos - SP",
      "decisor": { "nome": "Dr. João", "cargo": "Diretor" },
      "contatos": { "email_principal": "contato@clinica.com", "email_tipo": "generico" },
      "confianca": "alta"
    }
  ]
}
```

### 2. Processe com IA

Clique em **"🧠 Processar com IA"**. O sistema irá:
- Analisar cada lead com GPT-5 mini
- Calcular scores contextuais (0-100)
- Gerar insights estratégicos
- Verificar duplicatas nos últimos 180 dias
- Mostrar mensagem **"PRONTO!"** ao finalizar

### 3. Revise a Fila de Envio

Na aba **"📊 Fila de Envio"**:
- ⚠️ **Leads duplicados**: Aparecem primeiro para você aprovar ou ignorar
- 📋 **Fila ordenada**: Leads por score (maior primeiro)
- 👁️ **Preview**: Veja o email que será enviado (gerado pela IA)
- ▶️ **Iniciar Envio**: Começa envio com delays inteligentes

### 4. Gere o Relatório

Clique em **"📄 Gerar Relatório PDF"** para criar documento com:
- Resumo da campanha
- Lista de emails enviados
- Estatísticas de sucesso/falha

O PDF é salvo automaticamente na sua Área de Trabalho.

## ⚙️ Configuração

Edite `config/settings.py`:

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| DAILY_EMAIL_LIMIT | 10 | Emails por dia |
| WORK_HOURS_START | 9 | Início (hora) |
| WORK_HOURS_END | 18 | Fim (hora) |
| DELAY_MEAN | 90 | Delay médio (seg) |
| MAX_ATTEMPTS_PER_LEAD | 2 | Tentativas/lead |

## 📁 Estrutura do Projeto

```
email_abaplay_resend/
├── app/
│   ├── main.py              # Interface Streamlit
│   ├── database.py          # SQLite + verificação duplicatas
│   ├── email_sender.py      # Integração Resend + preview
│   ├── lead_processor.py    # Parsing & scoring
│   ├── llm_processor.py     # 🧠 Integração LangChain/OpenAI
│   ├── delay_manager.py     # Delays gaussianos
│   ├── template_engine.py   # Templates de email
│   └── report_generator.py  # Geração PDF
├── config/
│   └── settings.py          # Configurações centralizadas
├── data/
│   └── email_automation.db  # Banco SQLite
├── scripts/
│   ├── add_leads.py         # Adicionar leads manualmente
│   └── migrate_leads_sheet.py
├── requirements.txt
├── .env                     # Variáveis de ambiente (não versionado)
├── .env.example
├── .gitignore
└── README.md
```

## 🔧 Scripts Utilitários

### add_leads.py

Script para adicionar leads manualmente na planilha com dados completos. Útil para:
- Corrigir leads que não foram registrados
- Importar leads de fontes externas
- Migração de dados

**Como módulo:**
```python
from scripts.add_leads import add_leads_to_sheet

leads = [
    {
        "nome_clinica": "Clínica Exemplo",
        "endereco": "Rua X, 123",
        "cidade_uf": "São Paulo - SP",
        "contatos": {
            "email_principal": "contato@clinica.com",
            "telefone": "(11) 1234-5678"
        },
        "decisor": {"nome": "Dr. João", "cargo": "Diretor"},
        "contexto_abordagem": {
            "resumo_clinica": "...",
            "dor_provavel": "...",
            "tom_sugerido": "consultivo"
        }
    }
]

stats = add_leads_to_sheet(leads, campaign_id="minha_campanha")
print(f"Adicionados: {stats['added']}")
```

**Via JSON:**
```python
from scripts.add_leads import add_leads_from_json

json_data = '{"leads": [...]}'
add_leads_from_json(json_data, campaign_id="import_2024")
```

## 🛡️ Práticas Anti-Spam

| Prática | Implementação |
|---------|---------------|
| Delays inteligentes | Distribuição gaussiana (média 90s) |
| Horário comercial | 9h-18h, seg-sex |
| Limite diário | 10 emails (warmup) |
| Blacklist | Opt-outs respeitados |
| Verificação duplicatas | 180 dias com aprovação manual |
| Headers | List-Unsubscribe automático |
| Validação MX | Verifica se domínio existe |

## 👤 Assinatura dos Emails

```
---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com "REMOVER".
```

## 📄 Licença

Uso interno ABAplay.
