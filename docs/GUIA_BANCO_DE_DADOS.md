# 🗄️ Guia do Banco de Dados — Sistema de Automação de Emails ABAplay

> **Última atualização:** 2026-02-25

---

## 1. Visão Geral da Arquitetura

O sistema de automação de emails da ABAplay utiliza um banco de dados **PostgreSQL** para armazenar campanhas, leads, logs de emails, blacklist e configurações.

### Histórico de Migrações

| Período | Armazenamento | Motivo da mudança |
|---|---|---|
| v1.0 | Google Sheets (via `gspread`) | MVP rápido |
| v2.0 | Neon PostgreSQL (gratuito) | Problemas de confiabilidade no Sheets |
| v3.0 (planejado) | Render PostgreSQL (compartilhado) | Neon chegando no limite gratuito |

---

## 2. Banco de Dados Atual: Neon PostgreSQL

### Conexão

```
DATABASE_URL=postgresql://neondb_owner:NEON_PASSWORD_REDACTED@ep-dawn-firefly-a83lnrqc-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require
```

- **Host:** `ep-dawn-firefly-a83lnrqc-pooler.eastus2.azure.neon.tech`
- **Database:** `neondb`
- **User:** `neondb_owner`
- **Schema:** `public`
- **Driver:** `psycopg2` (Python)
- **Connection pooling:** Neon pooler (incluso na URL)
- **SSL:** Obrigatório (`sslmode=require`)

### Tabelas e Tamanhos (em 2026-02-25)

| Tabela | Descrição | Rows | Tamanho |
|---|---|---|---|
| `campaigns` | Campanhas de prospecção | 155 | 72 KB |
| `leads` | Leads/clínicas prospectadas | 1353 | 3.8 MB |
| `email_log` | Registro de emails enviados | 625 | 824 KB |
| `blacklist` | Emails bloqueados | 7 | 80 KB |
| `email_events` | Eventos de email (futuro) | 0 | 64 KB |
| `settings` | Configurações da aplicação | 7 | 32 KB |
| **Total** | | **~2147** | **~12.5 MB** |

---

## 3. Banco de Dados de Produção: Render PostgreSQL (ABAplay principal)

### Conexão

```
DATABASE_URL=postgresql://abaplay_postgres_db_user:RENDER_PASSWORD_REDACTED@dpg-d07n3madbo4c73ehoiqg-a.oregon-postgres.render.com/abaplay_postgres_db
```

- **Host:** `dpg-d07n3madbo4c73ehoiqg-a.oregon-postgres.render.com`
- **Database:** `abaplay_postgres_db`
- **User:** `abaplay_postgres_db_user`
- **Database ID (Render):** `dpg-d07n3madbo4c73ehoiqg-a`
- **Workspace ID (Render):** `tea-d07me5adbo4c73ehaebg`
- **Schema:** `public` (55 tabelas da plataforma clínica)
- **Plano:** Pago (sub-utilizado)

### ⚠️ Como Conectar ao Render DB

> **Importante:** O Render **bloqueia conexões externas** diretas (via `psql`, DBeaver, etc.). A forma de conectar é via **Render CLI**.

#### Instalação e Login (já feitos)

```bash
# CLI instalada em: /home/gabriel/.local/bin/render
# Config em: /home/gabriel/.render/cli.yaml
# Login já realizado - API key válida
```

#### Executar SQL no Render (modo não-interativo)

```bash
# Sintaxe
render psql <database-id> -c "<SQL>" -o json

# Exemplos:
render psql dpg-d07n3madbo4c73ehoiqg-a -c "SELECT COUNT(*) FROM users;" -o json
render psql dpg-d07n3madbo4c73ehoiqg-a -c "\dt" -o json
render psql dpg-d07n3madbo4c73ehoiqg-a -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';" -o json
```

#### Modo Interativo (seleção por menu)

```bash
render psql
# Irá exibir menu interativo para selecionar o banco
# Use Enter para selecionar, Ctrl+C para sair
```

### Tabelas no Render (55 tabelas em `public`)

```
ai_audit_logs                    notifications
ai_usage_logs                    notificationstatus
availability_changes_log         objectives
billing_audit_log                parent_therapist_chat
billing_automation_config        patient_emergency_contacts
billing_communications           patient_medical_history
billing_notifications            patient_medications
billing_templates                patient_professional_contacts
case_discussions                 patient_program_assignments
clinic_ai_settings               patient_program_progress
clinic_billing                   patient_therapist_preferences
clinic_discipline_settings       patients
clinic_rooms                     payment_methods
clinics                          program_areas
disciplines                      program_sessions
email_tracking                   program_step_instructions
family_activities                program_steps
family_area_templates            program_sub_areas
migrations                       programs
                                 prompt_level_change_log
                                 recurring_appointment_templates
                                 scheduled_sessions
                                 subscription_analytics
                                 subscription_plan_prices
                                 super_admin_ai_logs
                                 supervisor_chat_*  (5 tabelas)
                                 therapist_absences
                                 therapist_availability_template
                                 therapist_patient_assignments
                                 therapist_specialties
                                 trial_history
                                 users
```

---

## 4. Análise de Viabilidade: Migrar Neon → Render

### Resumo Executivo

| Pergunta | Resposta |
|---|---|
| É viável? | **Sim**, totalmente |
| Risco para produção? | **Mínimo**, com schema separado o isolamento é completo |
| Quanto trabalho no código? | **Quase zero** — trocar 1 variável `.env` + 1-2 linhas em `database.py` |
| Benefício financeiro? | Elimina custo do Neon sem custo adicional |
| Complexidade da migração? | Baixa — `pg_dump` + Render CLI |

### Estratégia: Schema PostgreSQL Separado

```
abaplay_postgres_db (database)
├── public          ← 55 tabelas da ABAplay produção (NÃO MEXER)
└── sdr             ← 6 tabelas do sistema de emails (NOVO)
```

PostgreSQL suporta múltiplos **schemas** dentro do mesmo database. Cada schema funciona como um namespace independente:
- `public.users` ≠ `sdr.campaigns` → completamente isolados
- Queries da ABAplay usam `public` e nunca acessam `sdr`
- Queries do email system usam `sdr` via `search_path`

### Conflito de Nomes: ZERO ✅

Nenhuma das 6 tabelas do email system (`campaigns`, `leads`, `email_log`, `blacklist`, `email_events`, `settings`) existe no schema `public` do Render. **Confirmado via query direta em 2026-02-25.**

### Mudanças Necessárias na Aplicação

| Arquivo | O que muda | Linhas |
|---|---|---|
| `.env` | Trocar `DATABASE_URL` do Neon para Render (com `search_path=sdr`) | 1 |
| `app/database.py` | Adicionar `SET search_path TO sdr` no `get_connection()` | ~2 |
| Todo o resto | **Nada** — as queries SQL usam nomes de tabela sem schema | 0 |

### Como Funciona na Prática

**1. Criar o schema `sdr` no Render (uma vez):**
```sql
CREATE SCHEMA IF NOT EXISTS sdr;
```

**2. Criar as 6 tabelas dentro de `sdr`:**  
As mesmas DDLs do Neon, mas dentro do schema `sdr`.

**3. Migrar dados Neon → Render:**
```bash
# Dump do Neon
pg_dump "postgresql://...@neon.tech/neondb" --schema=public --data-only > neon_dump.sql

# Ajustar para schema sdr e importar via Render CLI
# (ou script Python que lê do Neon e grava no Render)
```

**4. Alterar a conexão no `.env`:**
```bash
# Antes (Neon):
DATABASE_URL=postgresql://...@neon.tech/neondb?sslmode=require

# Depois (Render com schema sdr):
DATABASE_URL=postgresql://...@render.com/abaplay_postgres_db?options=-csearch_path%3Dsdr
```

**5. Ou setar search_path no código (`database.py`):**
```python
def get_connection():
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg2.connect(DATABASE_URL)
        _connection.autocommit = True
        with _connection.cursor() as cur:
            cur.execute("SET search_path TO sdr")
    return _connection
```

### Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Impacto no banco de produção | Muito Baixa | Schema `sdr` é completamente isolado |
| Performance | Zero | ~12.5 MB adicionais é insignificante |
| Conflito de tabela/nome | Zero | Schemas diferentes = zero conflito |
| Perda de dados na migração | Baixa | Manter Neon ativo como fallback até validar |
| Usuário sem permissão CREATE SCHEMA | Baixa | `abaplay_postgres_db_user` é owner do DB |
| Conectividade (app → Render) | Baixa | App do email já roda local/Streamlit Cloud; Render aceita conexões externas via API |

---

## 5. Schema do Banco de Dados (email system)

### 5.1 `campaigns`

```sql
CREATE TABLE campaigns (
    id VARCHAR(8) PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'paused', 'completed', 'cancelled')),
    total_leads INTEGER DEFAULT 0,
    emails_sent INTEGER DEFAULT 0,
    emails_failed INTEGER DEFAULT 0
);
```

### 5.2 `leads`

```sql
CREATE TABLE leads (
    id VARCHAR(8) PRIMARY KEY,
    campaign_id VARCHAR(8) NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'new'
        CHECK (status IN ('new', 'queued', 'contacted', 'responded', 'converted', 'lost', 'invalid')),
    nome_clinica TEXT DEFAULT '',
    endereco TEXT DEFAULT '',
    cidade_uf TEXT DEFAULT '',
    cnpj TEXT DEFAULT '',
    site TEXT DEFAULT '',
    decisor_nome TEXT DEFAULT '',
    decisor_cargo TEXT DEFAULT '',
    decisor_linkedin TEXT DEFAULT '',
    email_principal TEXT DEFAULT '',
    email_tipo VARCHAR(20) DEFAULT '',
    telefone TEXT DEFAULT '',
    whatsapp TEXT DEFAULT '',
    instagram TEXT DEFAULT '',
    fonte TEXT DEFAULT '',
    confianca VARCHAR(10) DEFAULT ''
        CHECK (confianca IN ('', 'alta', 'media', 'baixa')),
    score INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 100),
    resumo_clinica TEXT DEFAULT '',
    perfil_decisor TEXT DEFAULT '',
    gancho_personalizacao TEXT DEFAULT '',
    dor_provavel TEXT DEFAULT '',
    tom_sugerido VARCHAR(20) DEFAULT '',
    notas TEXT DEFAULT '',
    motivo_descarte TEXT DEFAULT '',
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leads_campaign_id ON leads(campaign_id);
CREATE INDEX idx_leads_email_principal ON leads(email_principal);
CREATE INDEX idx_leads_cidade_uf ON leads(cidade_uf);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_score ON leads(score DESC);
```

### 5.3 `email_log`

```sql
CREATE TABLE email_log (
    id VARCHAR(8) PRIMARY KEY,
    lead_id VARCHAR(8) REFERENCES leads(id) ON DELETE SET NULL,
    campaign_id VARCHAR(8) REFERENCES campaigns(id) ON DELETE SET NULL,
    email_to TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body_html TEXT DEFAULT '',
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'failed', 'bounced', 'rejected')),
    attempt_number INTEGER DEFAULT 1,
    resend_id TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_log_lead_id ON email_log(lead_id);
CREATE INDEX idx_email_log_campaign_id ON email_log(campaign_id);
CREATE INDEX idx_email_log_email_to ON email_log(email_to);
CREATE INDEX idx_email_log_sent_at ON email_log(sent_at);
CREATE INDEX idx_email_log_status ON email_log(status);
CREATE INDEX idx_email_log_status_sent_at ON email_log(status, sent_at) WHERE status = 'sent';
```

### 5.4 `blacklist`

```sql
CREATE TABLE blacklist (
    id VARCHAR(8) PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    domain TEXT GENERATED ALWAYS AS (split_part(email, '@', 2)) STORED,
    reason VARCHAR(30) DEFAULT 'user_request'
        CHECK (reason IN ('user_request', 'hard_bounce', 'spam_complaint', 'manual', 'invalid_email')),
    source_campaign_id VARCHAR(8) REFERENCES campaigns(id) ON DELETE SET NULL,
    added_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_blacklist_email ON blacklist(email);
CREATE INDEX idx_blacklist_domain ON blacklist(domain);
```

### 5.5 `email_events` (preparada para webhooks futuros)

```sql
CREATE TABLE email_events (
    id SERIAL PRIMARY KEY,
    email_log_id VARCHAR(8) REFERENCES email_log(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL
        CHECK (event_type IN ('delivered', 'opened', 'clicked', 'bounced', 'complained', 'unsubscribed')),
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_events_log_id ON email_events(email_log_id);
CREATE INDEX idx_email_events_type ON email_events(event_type);
```

### 5.6 `settings`

```sql
CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Valores padrão
INSERT INTO settings (key, value, description) VALUES
    ('daily_email_limit', '20', 'Limite diário de envio de emails'),
    ('duplicate_check_days', '180', 'Dias para considerar email como duplicata'),
    ('work_hours_start', '9', 'Hora de início dos envios'),
    ('work_hours_end', '18', 'Hora de fim dos envios'),
    ('delay_mean', '90', 'Média de delay entre envios (segundos)'),
    ('delay_std', '30', 'Desvio padrão do delay (segundos)'),
    ('max_attempts_per_lead', '2', 'Máximo de tentativas por lead');
```

---

## 6. Como o Código se Conecta ao Banco

### Fluxo de Conexão

```
.env (DATABASE_URL)
  ↓
config/settings.py (_get_secret → DATABASE_URL)
  ↓
app/database.py (get_connection → psycopg2.connect)
  ↓
get_cursor() → RealDictCursor (context manager)
  ↓
Todas as funções usam get_cursor() para queries
```

### Padrões do Código

**Conexão reutilizável (singleton):**
```python
_connection = None

def get_connection():
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg2.connect(DATABASE_URL)
        _connection.autocommit = True
    return _connection
```

**Cursor como context manager:**
```python
@contextmanager
def get_cursor():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()
```

**Uso padrão em funções:**
```python
def get_campaign(campaign_id: str):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None
```

**Geração de IDs:**
```python
def _generate_id() -> str:
    return str(uuid.uuid4())[:8]  # 8 caracteres hex
```

**Conversão de rows:**
- `RealDictCursor` retorna `RealDictRow` (dict-like)
- `_row_to_dict()` converte para dict puro, timestamps para ISO string, None para ''

### Cache em Memória

O módulo `app/cache.py` implementa cache para queries frequentes:
- **Blacklist:** cache de 5 minutos (evita query a cada verificação)
- **Contagem diária:** cache de 1 minuto (emails enviados hoje)

### Dependências

```
psycopg2-binary>=2.9.0  # Driver PostgreSQL (em requirements.txt)
```

---

## 7. Mapa de Funções do `database.py`

### Campanhas
| Função | Descrição |
|---|---|
| `create_campaign(name, region)` | Cria campanha, retorna ID |
| `get_campaign(campaign_id)` | Retorna dados da campanha |
| `update_campaign_stats(...)` | Atualiza contadores |
| `get_campaign_summary()` | Resumo com métricas (JOINs) |

### Leads
| Função | Descrição |
|---|---|
| `insert_lead(campaign_id, lead_data)` | Insere lead, retorna ID |
| `get_lead(lead_id)` | Retorna dados do lead |
| `get_leads_by_campaign(campaign_id)` | Leads de uma campanha (por score) |
| `update_lead_score(lead_id, score)` | Atualiza score (0-100) |
| `update_lead_status(lead_id, status)` | Muda status do lead |
| `update_lead_notes(lead_id, notas)` | Atualiza notas |
| `get_leads_by_status(status)` | Filtra por status |

### Email Log
| Função | Descrição |
|---|---|
| `log_email_attempt(...)` | Registra tentativa de envio |
| `update_email_status(log_id, status)` | Atualiza status do email |
| `get_email_attempts(lead_id)` | Contagem de tentativas |
| `get_emails_sent_today()` | Total enviados hoje (com cache) |
| `get_email_log_by_campaign(campaign_id)` | Histórico por campanha |
| `get_all_sent_emails(...)` | Paginação + filtros |
| `check_email_sent_recently(email, days)` | Detecção de duplicatas |
| `get_email_history(email)` | Histórico completo de um email |
| `check_leads_for_duplicates(leads, days)` | Verificação em lote |

### Blacklist
| Função | Descrição |
|---|---|
| `add_to_blacklist(email, reason)` | Adiciona à blacklist |
| `is_blacklisted(email)` | Verifica (com cache) |
| `get_blacklist()` | Lista completa |
| `remove_from_blacklist(email)` | Remove da blacklist |
| `add_multiple_to_blacklist(emails)` | Importação em lote |

### Settings
| Função | Descrição |
|---|---|
| `get_setting(key, default)` | Busca configuração |
| `set_setting(key, value)` | Atualiza configuração |
| `get_all_settings()` | Todas as configurações |

### Utilitários
| Função | Descrição |
|---|---|
| `load_table_as_dataframe(table_name)` | Carrega tabela como Pandas DataFrame |
| `get_daily_send_stats(days)` | Envios por dia (gráficos) |
| `insert_email_event(...)` | Registra evento de email |
| `get_email_events(email_log_id)` | Eventos de um email |

---

## 8. Diagrama de Relacionamentos

```
campaigns (1) ──────── (N) leads
    │                         │
    │                         │
    ├── (N) email_log ────────┘
    │       │
    │       └── (N) email_events
    │
    └── (N) blacklist (source_campaign_id, opcional)

settings (independente, chave-valor)
```

---

*Documento gerado em 2026-02-25. Manter atualizado após migrações.*
