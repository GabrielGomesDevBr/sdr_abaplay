# Plano de Migra\u00e7\u00e3o: Google Sheets \u2192 Neon PostgreSQL

## Vis\u00e3o Geral

Migrar o armazenamento de dados do sistema de automa\u00e7\u00e3o de emails da ABAplay, atualmente baseado em Google Sheets (via `gspread`), para um banco de dados PostgreSQL hospedado no **Neon**. Aproveitar a refatora\u00e7\u00e3o para corrigir problemas estruturais e adicionar funcionalidades que o Google Sheets n\u00e3o suportava.

### Motiva\u00e7\u00e3o
- Problemas frequentes de confiabilidade ao gravar dados na planilha (race conditions, `append_row` perdendo dados)
- Limita\u00e7\u00f5es da API do Google Sheets (rate limits, lat\u00eancia)
- Falta de integridade referencial (foreign keys)
- Aus\u00eancia de \u00edndices para buscas eficientes
- Dificuldade de escalar com o crescimento dos dados

### O que muda com esta migra\u00e7\u00e3o
| Antes (Sheets) | Depois (Neon SQL) |
|---|---|
| 4 abas sem rela\u00e7\u00e3o formal | 6 tabelas com FKs e constraints |
| `append_row()` perde dados | `INSERT` at\u00f4mico com transa\u00e7\u00f5es |
| Busca = scan da aba inteira | Queries com \u00edndices, JOINs, filtros no SQL |
| Sem status do lead | Ciclo de vida completo do lead |
| Sem hist\u00f3rico de altera\u00e7\u00f5es | Tabela de eventos com audit trail |
| Email enviado = \u00fanico registro | Corpo do email armazenado + eventos de delivery |
| Configura\u00e7\u00f5es hardcoded | Tabela de configura\u00e7\u00f5es no banco |

---

## Fase 0: Prepara\u00e7\u00e3o

- [x] Salvar `DATABASE_URL` no `.env`
- [x] Criar branch `feat/migrate-to-neon-sql`

### Depend\u00eancias
Adicionar ao `requirements.txt`:
```
psycopg2-binary>=2.9.0    # Driver PostgreSQL
```

> **Nota:** Sem ORM. Usaremos `psycopg2` com queries SQL parametrizadas, mantendo a mesma interface p\u00fablica do `database.py`.

---

## Fase 1: Schema do Banco de Dados

### 1.1 Tabela `campaigns` (existente, melhorada)
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

**Colunas novas:**
| Coluna | Motivo |
|---|---|
| `description` | Descri\u00e7\u00e3o livre da campanha (regi\u00e3o alvo, objetivo) |
| `updated_at` | Saber quando a campanha foi modificada pela \u00faltima vez |
| `status CHECK` | Constraint para evitar status inv\u00e1lidos + novos status `paused` e `cancelled` |

---

### 1.2 Tabela `leads` (existente, melhorada)
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
    -- Campos contexto_abordagem (v3.0)
    resumo_clinica TEXT DEFAULT '',
    perfil_decisor TEXT DEFAULT '',
    gancho_personalizacao TEXT DEFAULT '',
    dor_provavel TEXT DEFAULT '',
    tom_sugerido VARCHAR(20) DEFAULT '',
    -- Novos campos
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

**Colunas novas:**
| Coluna | Motivo |
|---|---|
| `status` | **Ciclo de vida do lead.** Hoje n\u00e3o se sabe se um lead j\u00e1 foi contatado, respondeu, converteu ou foi descartado. Com este campo: `new` \u2192 `queued` (na fila) \u2192 `contacted` (email enviado) \u2192 `responded` / `converted` / `lost` |
| `notas` | Anota\u00e7\u00f5es livres sobre o lead (ex: "falei por telefone, interessado") |
| `motivo_descarte` | Quando `status = 'lost'` ou `'invalid'`, registrar o porqu\u00ea (ex: "email inv\u00e1lido", "n\u00e3o \u00e9 cl\u00ednica ABA") |
| `updated_at` | Rastrear \u00faltima modifica\u00e7\u00e3o |
| `CHECK` constraints | Validar `confianca`, `score` (0-100), `status` no banco |

---

### 1.3 Tabela `email_log` (existente, melhorada)
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
-- \u00cdndice composto para a query mais frequente: "emails enviados hoje"
CREATE INDEX idx_email_log_status_sent_at ON email_log(status, sent_at)
    WHERE status = 'sent';
```

**Colunas novas:**
| Coluna | Motivo |
|---|---|
| `body_html` | **Armazenar o corpo do email enviado.** Hoje o conte\u00fado \u00e9 gerado e enviado mas nunca salvo \u2014 n\u00e3o d\u00e1 pra saber o que foi enviado para cada lead. Essencial para auditoria e debug |
| `status` expandido | Novos status `bounced` e `rejected` para rastrear entregas que falharam ap\u00f3s o envio (webhooks do Resend) |
| `ON DELETE SET NULL` | Se um lead for removido, o log permanece (n\u00e3o perde hist\u00f3rico) |
| \u00cdndice composto | Otimiza a query `get_emails_sent_today()` que roda a cada envio |

---

### 1.4 Tabela `blacklist` (existente, melhorada)
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

**Colunas novas:**
| Coluna | Motivo |
|---|---|
| `domain` (generated) | Coluna computada automaticamente. Permite consultas por dom\u00ednio (ex: "quantos bounces do @gmail.com?") sem custo de manuten\u00e7\u00e3o |
| `reason` CHECK | Categorizar motivos: pediu remo\u00e7\u00e3o, bounce, spam, manual, email inv\u00e1lido |
| `source_campaign_id` | Saber qual campanha causou o bloqueio (rastreabilidade) |

---

### 1.5 Tabela `email_events` (NOVA)
```sql
CREATE TABLE email_events (
    id SERIAL PRIMARY KEY,
    email_log_id VARCHAR(8) REFERENCES email_log(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL
        CHECK (event_type IN (
            'delivered', 'opened', 'clicked', 'bounced',
            'complained', 'unsubscribed'
        )),
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_events_log_id ON email_events(email_log_id);
CREATE INDEX idx_email_events_type ON email_events(event_type);
```

**Por que essa tabela \u00e9 importante:**
Hoje o sistema envia emails mas **n\u00e3o sabe se foram entregues, abertos ou clicados**. O Resend oferece webhooks que enviam esses eventos. Com esta tabela:
- Saber taxa de abertura real por campanha
- Detectar hard bounces automaticamente e adicionar \u00e0 blacklist
- Identificar leads engajados (abriram/clicaram) para priorizar follow-up
- Detectar spam complaints e parar envios imediatamente

> **Implementa\u00e7\u00e3o do webhook**: ser\u00e1 uma fase futura (requer endpoint HTTP). Por ora, a tabela j\u00e1 fica pronta para quando o webhook for integrado.

---

### 1.6 Tabela `settings` (NOVA)
```sql
CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Valores iniciais
INSERT INTO settings (key, value, description) VALUES
    ('daily_email_limit', '20', 'Limite di\u00e1rio de envio de emails'),
    ('duplicate_check_days', '180', 'Dias para considerar email como duplicata'),
    ('work_hours_start', '9', 'Hora de in\u00edcio dos envios'),
    ('work_hours_end', '18', 'Hora de fim dos envios'),
    ('delay_mean', '90', 'M\u00e9dia de delay entre envios (segundos)'),
    ('delay_std', '30', 'Desvio padr\u00e3o do delay (segundos)'),
    ('max_attempts_per_lead', '2', 'M\u00e1ximo de tentativas por lead');
```

**Por que essa tabela \u00e9 importante:**
Hoje todos os par\u00e2metros est\u00e3o hardcoded no `settings.py` ou salvos em `data/user_config.json`. Problemas:
- `daily_email_limit` \u00e9 salvo em JSON local (perde em deploy)
- `duplicate_check_days` = 180 hardcoded, n\u00e3o configur\u00e1vel
- Delays, hor\u00e1rios de trabalho = hardcoded

Com a tabela `settings`:
- Configura\u00e7\u00f5es persistem no banco
- Alter\u00e1veis via UI sem deploy
- Cada configura\u00e7\u00e3o tem descri\u00e7\u00e3o para documenta\u00e7\u00e3o

---

## Fase 2: Migra\u00e7\u00e3o de Dados Existentes

### 2.1 Script de migra\u00e7\u00e3o (`scripts/migrate_to_sql.py`)
O script far\u00e1:
1. Conectar ao Google Sheets e ler TODOS os dados das 4 abas
2. Conectar ao Neon PostgreSQL
3. Criar as tabelas (DDL da Fase 1)
4. Inserir dados na ordem correta (respeitando foreign keys):
   - `campaigns` primeiro
   - `leads` segundo (depende de `campaigns`)
   - `email_log` terceiro (depende de `leads` e `campaigns`)
   - `blacklist` por \u00faltimo (independente)
   - `settings` com valores default
5. **Preencher campos novos com base nos dados existentes:**
   - `leads.status`: se tem email_log com `status='sent'` \u2192 `'contacted'`, sen\u00e3o \u2192 `'new'`
   - `blacklist.reason`: registros existentes \u2192 `'user_request'`
   - `campaigns.updated_at`: copiar de `created_at`
6. Validar contagens (rows no Sheets == rows no SQL)
7. Gerar relat\u00f3rio de migra\u00e7\u00e3o

### 2.2 Tratamento de dados
- Campos vazios na planilha \u2192 `NULL` ou `''` no SQL conforme o tipo
- `raw_data` (texto JSON) \u2192 `JSONB` nativo
- Timestamps ISO string \u2192 `TIMESTAMPTZ`
- Campos num\u00e9ricos em texto \u2192 `INTEGER` com fallback para 0
- Emails na blacklist \u2192 `LOWER()` para consist\u00eancia
- IDs duplicados ou inv\u00e1lidos \u2192 gerar novos UUIDs (com log)
- Registros \u00f3rf\u00e3os (email_log sem lead v\u00e1lido) \u2192 manter com `lead_id = NULL`

### 2.3 Valida\u00e7\u00e3o p\u00f3s-migra\u00e7\u00e3o
- Comparar contagem de registros por tabela
- Verificar integridade referencial
- Listar registros \u00f3rf\u00e3os que precisaram de ajuste
- Amostrar dados e comparar com planilha original

---

## Fase 3: Refatora\u00e7\u00e3o do `database.py`

### Estrat\u00e9gia
Substituir a implementa\u00e7\u00e3o interna do `database.py` mantendo a **mesma interface p\u00fablica** (mesmos nomes de fun\u00e7\u00e3o, mesmos par\u00e2metros, mesmos retornos). Assim, `main.py`, `email_sender.py`, `lead_processor.py` etc. n\u00e3o precisam mudar. Fun\u00e7\u00f5es novas ser\u00e3o adicionadas para as features novas.

### 3.1 Conex\u00e3o com o banco
```python
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

_connection = None

def get_connection():
    """Retorna conex\u00e3o reutiliz\u00e1vel (reconecta se necess\u00e1rio)"""
    ...

@contextmanager
def get_cursor():
    """Context manager para cursor com auto-commit"""
    ...
```

### 3.2 Mapeamento de fun\u00e7\u00f5es existentes (Sheets \u2192 SQL)

| Fun\u00e7\u00e3o | Antes | Depois |
|---|---|---|
| `create_campaign()` | `ws.append_row()` | `INSERT INTO campaigns ...` |
| `get_campaign()` | `ws.find()` + `ws.row_values()` | `SELECT * FROM campaigns WHERE id = %s` |
| `update_campaign_stats()` | `ws.find()` + `ws.update_cell()` \u00d7N | `UPDATE campaigns SET ... WHERE id = %s` |
| `insert_lead()` | `ws.append_row()` | `INSERT INTO leads ... RETURNING id` |
| `get_lead()` | `ws.find()` + `ws.row_values()` | `SELECT * FROM leads WHERE id = %s` |
| `get_leads_by_campaign()` | scan + filtro Python | `SELECT * FROM leads WHERE campaign_id = %s ORDER BY score DESC` |
| `update_lead_score()` | `ws.find()` + `ws.update_cell()` | `UPDATE leads SET score = %s WHERE id = %s` |
| `log_email_attempt()` | `ws.get_all_values()` + `ws.insert_row()` | `INSERT INTO email_log ...` |
| `update_email_status()` | `ws.find()` + `ws.update_cell()` \u00d7N | `UPDATE email_log SET ... WHERE id = %s` |
| `get_email_attempts()` | scan + count Python | `SELECT COUNT(*) FROM email_log WHERE lead_id = %s` |
| `get_emails_sent_today()` | scan + filtro Python | `SELECT COUNT(*) FROM email_log WHERE status = 'sent' AND sent_at::date = CURRENT_DATE` |
| `get_email_log_by_campaign()` | scan + filtro + join Python | `SELECT el.*, l.nome_clinica FROM email_log el LEFT JOIN leads l ...` |
| `get_email_history()` | scan + filtro Python | `SELECT el.*, l.nome_clinica, c.name FROM email_log el LEFT JOIN ...` |
| `check_email_sent_recently()` | scan + filtro Python | `SELECT * FROM email_log WHERE ... LIMIT 1` |
| `check_leads_for_duplicates()` | scan tudo + mapa Python | `SELECT DISTINCT LOWER(email_to) FROM email_log WHERE ...` |
| `is_blacklisted()` | scan + set Python | `SELECT 1 FROM blacklist WHERE email = %s` (+ cache) |
| `add_to_blacklist()` | `ws.append_row()` | `INSERT ... ON CONFLICT (email) DO NOTHING` |
| `get_blacklist()` | scan tudo | `SELECT * FROM blacklist ORDER BY added_at DESC` |

### 3.3 Fun\u00e7\u00f5es NOVAS a adicionar

```python
# --- Lead status management ---
def update_lead_status(lead_id: str, status: str, motivo: str = None):
    """Atualiza status do lead (new \u2192 queued \u2192 contacted \u2192 responded/converted/lost)"""

def update_lead_notes(lead_id: str, notas: str):
    """Adiciona/atualiza notas do lead"""

def get_leads_by_status(status: str, campaign_id: str = None) -> List[Dict]:
    """Busca leads por status, opcionalmente filtrado por campanha"""

# --- Email body storage ---
def log_email_attempt(lead_id, campaign_id, email_to, subject, attempt_number=1, body_html=''):
    """Agora aceita body_html para armazenar o conte\u00fado enviado"""

# --- Settings management ---
def get_setting(key: str, default: str = None) -> str:
    """Busca configura\u00e7\u00e3o do banco"""

def set_setting(key: str, value: str):
    """Atualiza configura\u00e7\u00e3o no banco"""

def get_all_settings() -> Dict[str, str]:
    """Retorna todas as configura\u00e7\u00f5es"""

# --- Email events (para uso futuro com webhooks) ---
def insert_email_event(email_log_id: str, event_type: str, payload: dict = None):
    """Registra evento de email (delivered, opened, bounced, etc.)"""

def get_email_events(email_log_id: str) -> List[Dict]:
    """Retorna eventos de um email"""

# --- Data loader para dashboard ---
def load_table_as_dataframe(table_name: str) -> pd.DataFrame:
    """Carrega tabela inteira como DataFrame (para data_viewer.py)"""

# --- Analytics helpers ---
def get_campaign_summary() -> List[Dict]:
    """Retorna resumo de todas as campanhas com m\u00e9tricas calculadas"""

def get_daily_send_stats(days: int = 30) -> List[Dict]:
    """Retorna contagem de emails por dia (para gr\u00e1ficos)"""
```

### 3.4 O que manter
- **Cache em mem\u00f3ria**: `cache.py` inalterado (blacklist 5min, daily count 1min)
- **Interface p\u00fablica existente**: mesmos nomes, par\u00e2metros e retornos
- **Gera\u00e7\u00e3o de IDs**: `uuid4()[:8]`
- **Formato de timestamps**: ISO string nos retornos para compatibilidade

### 3.5 O que remover
- Toda depend\u00eancia de `gspread` e `google-auth` no `database.py`
- Vari\u00e1veis `_client`, `_spreadsheet`, `_worksheets`
- Fun\u00e7\u00f5es `get_client()`, `get_spreadsheet()`, `get_worksheet()`
- `SHEET_COLUMNS`, `_row_to_dict()`

---

## Fase 4: Refatora\u00e7\u00e3o do `data_viewer.py`

### Mudan\u00e7as
- Substituir `load_data_as_df()` (que usa `get_worksheet().get_all_values()`) por `load_table_as_dataframe()` do novo `database.py`
- Remover import de `get_worksheet` e `SHEET_COLUMNS`
- Aproveitar para adicionar m\u00e9tricas novas no dashboard:
  - KPI de leads por status (new/contacted/responded/converted)
  - Filtro por status do lead na tabela
  - Exibi\u00e7\u00e3o do corpo do email enviado no hist\u00f3rico

---

## Fase 5: Atualiza\u00e7\u00e3o do `config/settings.py`

### Adicionar
```python
DATABASE_URL = os.getenv("DATABASE_URL")
```

### Manter (para o script de migra\u00e7\u00e3o)
```python
GOOGLE_SHEETS_SPREADSHEET_ID    # Usado apenas pelo script de migra\u00e7\u00e3o
GOOGLE_SHEETS_CREDENTIALS_PATH  # Usado apenas pelo script de migra\u00e7\u00e3o
```

### Migrar para banco (l\u00f3gica)
Os valores hardcoded (`DAILY_EMAIL_LIMIT`, `WORK_HOURS_*`, `MAX_ATTEMPTS_PER_LEAD`, `DELAY_*`) continuam no `settings.py` como **fallback**, mas a fun\u00e7\u00e3o `get_setting()` prioriza o valor do banco. Isso permite alterar via UI sem redeploy.

---

## Fase 6: Adaptar `email_sender.py` (m\u00ednimo)

### Mudan\u00e7as pontuais
- Passar `body_html` para `log_email_attempt()` (novo par\u00e2metro)
- Ap\u00f3s envio com sucesso, chamar `update_lead_status(lead_id, 'contacted')`
- Estas s\u00e3o mudan\u00e7as de 2-3 linhas, sem refatora\u00e7\u00e3o

---

## Fase 7: Adaptar `main.py` (m\u00ednimo)

### Mudan\u00e7as pontuais
- Ao processar leads, setar status `'queued'` ao inv\u00e9s de n\u00e3o ter status
- Ler `daily_email_limit` via `get_setting()` ao inv\u00e9s de `user_config.json`
- Estas s\u00e3o mudan\u00e7as pontuais de poucas linhas

---

## Fase 8: Testes e Valida\u00e7\u00e3o

### 8.1 Testar conex\u00e3o
- Script para verificar conex\u00e3o com Neon
- Criar tabelas e verificar schema

### 8.2 Testar migra\u00e7\u00e3o
- Rodar script de migra\u00e7\u00e3o em modo dry-run
- Comparar contagens Sheets vs SQL
- Verificar dados de amostra

### 8.3 Testar funcionalidades
- Criar campanha
- Inserir lead
- Verificar status do lead muda corretamente
- Enviar email (log + body armazenado)
- Verificar blacklist
- Verificar detec\u00e7\u00e3o de duplicatas
- Dashboard carregando do SQL
- Settings lidos do banco
- Cache funcionando

---

## Fase 9: Limpeza

### Ap\u00f3s migra\u00e7\u00e3o confirmada
- Remover `gspread` e `google-auth` do `requirements.txt`
- Remover c\u00f3digo morto de Google Sheets
- Remover `data/user_config.json` (substitu\u00eddo pela tabela `settings`)
- Atualizar coment\u00e1rios/docstrings

### N\u00c3O remover
- `credentials.json` (backup)
- Scripts de migra\u00e7\u00e3o (refer\u00eancia hist\u00f3rica)
- Planilha original (backup de dados)

---

## Resumo das Melhorias por Tabela

### `campaigns` (+2 colunas)
| Melhoria | Impacto |
|---|---|
| `description` | Documenta\u00e7\u00e3o da campanha |
| `updated_at` | Rastreabilidade |
| CHECK em `status` | Dados consistentes |

### `leads` (+4 colunas)
| Melhoria | Impacto |
|---|---|
| `status` (ciclo de vida) | **Maior ganho.** Saber exatamente onde cada lead est\u00e1 no funil |
| `notas` | Anota\u00e7\u00f5es manuais sobre o lead |
| `motivo_descarte` | Entender por que leads foram perdidos |
| `updated_at` | Rastreabilidade |
| CHECK constraints | Dados sempre v\u00e1lidos |

### `email_log` (+1 coluna)
| Melhoria | Impacto |
|---|---|
| `body_html` | **Saber exatamente o que foi enviado** para cada lead |
| Status `bounced`/`rejected` | Rastrear falhas p\u00f3s-envio |
| \u00cdndice composto | Query `emails_sent_today` muito mais r\u00e1pida |

### `blacklist` (+2 colunas)
| Melhoria | Impacto |
|---|---|
| `domain` (computed) | An\u00e1lise por dom\u00ednio |
| `reason` categorizado | Entender por que emails foram bloqueados |
| `source_campaign_id` | Rastreabilidade da campanha causadora |

### `email_events` (TABELA NOVA)
| Melhoria | Impacto |
|---|---|
| Registrar opens/clicks/bounces | **Futuro.** Saber se emails foram abertos/clicados |
| Pronta para webhooks do Resend | Sem trabalho quando integrar |

### `settings` (TABELA NOVA)
| Melhoria | Impacto |
|---|---|
| Configura\u00e7\u00f5es no banco | Alter\u00e1veis via UI, persistem em qualquer deploy |
| Substitui `user_config.json` e hardcoded values | Fonte \u00fanica de verdade |

---

## Ordem de Execu\u00e7\u00e3o

```
Fase 0: Prepara\u00e7\u00e3o                        [CONCLU\u00cdDA]
  \u2514\u2500 .env configurado, branch criada

Fase 1: Schema SQL                         [ ]
  \u2514\u2500 Criar 6 tabelas no Neon

Fase 2: Migra\u00e7\u00e3o de dados                   [ ]
  \u2514\u2500 Script Sheets \u2192 SQL + preencher campos novos
  \u2514\u2500 Validar dados migrados

Fase 3: Refatorar database.py              [ ]
  \u2514\u2500 Substituir gspread por psycopg2
  \u2514\u2500 Fun\u00e7\u00f5es existentes + fun\u00e7\u00f5es novas

Fase 4: Refatorar data_viewer.py           [ ]
  \u2514\u2500 Adaptar load_data_as_df()
  \u2514\u2500 Adicionar m\u00e9tricas de status do lead

Fase 5: Atualizar settings.py              [ ]
  \u2514\u2500 DATABASE_URL + get_setting() como fonte prim\u00e1ria

Fase 6: Adaptar email_sender.py            [ ]
  \u2514\u2500 Salvar body_html + atualizar lead status

Fase 7: Adaptar main.py                    [ ]
  \u2514\u2500 Lead status + settings do banco

Fase 8: Testes                             [ ]
  \u2514\u2500 Conex\u00e3o, migra\u00e7\u00e3o, funcionalidades

Fase 9: Limpeza                            [ ]
  \u2514\u2500 Remover depend\u00eancias do Sheets
```

---

## Riscos e Mitiga\u00e7\u00f5es

| Risco | Mitiga\u00e7\u00e3o |
|---|---|
| Perda de dados na migra\u00e7\u00e3o | Script valida contagens; planilha mantida intacta |
| IDs duplicados/inv\u00e1lidos | Script gera novos UUIDs e loga |
| Foreign keys \u00f3rf\u00e3s | `ON DELETE SET NULL` onde apropriado; script reporta \u00f3rf\u00e3os |
| Conex\u00e3o Neon instável | Reconex\u00e3o autom\u00e1tica; Neon tem 99.95% SLA |
| Mudan\u00e7a quebra UI | Interface p\u00fablica do `database.py` mantida id\u00eantica |
| Rollback necess\u00e1rio | Branch separada; Google Sheets permanece ativo |

---

## Estimativa de Arquivos Alterados

| Arquivo | Tipo de altera\u00e7\u00e3o |
|---|---|
| `app/database.py` | **Reescrita completa** (mesma interface + fun\u00e7\u00f5es novas) |
| `app/data_viewer.py` | **Altera\u00e7\u00e3o moderada** (adaptar loader + m\u00e9tricas de status) |
| `app/email_sender.py` | **Altera\u00e7\u00e3o m\u00ednima** (+body_html, +update_lead_status) |
| `app/main.py` | **Altera\u00e7\u00e3o m\u00ednima** (+lead status, +get_setting) |
| `config/settings.py` | **Altera\u00e7\u00e3o m\u00ednima** (+DATABASE_URL) |
| `requirements.txt` | **Altera\u00e7\u00e3o m\u00ednima** (+psycopg2-binary) |
| `.env` | **J\u00e1 feita** (DATABASE_URL) |
| `scripts/migrate_to_sql.py` | **Arquivo novo** (migra\u00e7\u00e3o) |
