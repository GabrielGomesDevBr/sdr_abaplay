# Plano de Melhorias - ABAplay Email Automation

> Documento consolidado de melhorias técnicas e visuais para a aplicação.
> Data: 05/02/2026

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Melhorias Técnicas](#melhorias-técnicas)
3. [Melhorias Visuais (UI/UX)](#melhorias-visuais-uiux)
4. [Cronograma de Implementação](#cronograma-de-implementação)
5. [Checklist de Implementação](#checklist-de-implementação)

---

## Visão Geral

### Estado Atual
A aplicação funciona corretamente para o fluxo básico de automação de emails. No entanto, há oportunidades significativas de otimização em performance, experiência do usuário e manutenibilidade.

### Objetivos
- Reduzir chamadas à API do Google Sheets em ~80%
- Melhorar feedback visual ao usuário
- Tornar a interface mais moderna e profissional
- Facilitar manutenção futura do código

---

## Melhorias Técnicas

### Fase 1: Performance & Estabilidade (Crítico)

#### 1.1 Cache de Blacklist
**Arquivo:** `app/database.py`
**Problema:** `is_blacklisted()` carrega toda a planilha a cada verificação
**Impacto:** 100 leads = 100 chamadas API

```python
# Implementar cache com TTL
_blacklist_cache = set()
_blacklist_cache_time = 0
BLACKLIST_CACHE_TTL = 300  # 5 minutos

def is_blacklisted(email: str) -> bool:
    global _blacklist_cache, _blacklist_cache_time

    if time.time() - _blacklist_cache_time > BLACKLIST_CACHE_TTL:
        _refresh_blacklist_cache()

    return email.lower() in _blacklist_cache
```

#### 1.2 Cache de Contagem Diária
**Arquivo:** `app/database.py`
**Problema:** `get_emails_sent_today()` recalcula a cada render

```python
# Implementar cache com invalidação inteligente
_daily_count_cache = {"date": None, "count": 0}

def get_emails_sent_today() -> int:
    today = datetime.now().strftime('%Y-%m-%d')
    if _daily_count_cache["date"] == today:
        return _daily_count_cache["count"]
    # ... recalcula e atualiza cache
```

#### 1.3 Timeout no LLM
**Arquivo:** `app/llm_processor.py`
**Problema:** Chamadas ao LLM podem travar indefinidamente

```python
import asyncio

async def process_with_timeout(coro, timeout=30):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": "Timeout na chamada ao LLM"}
```

#### 1.4 Batch Updates no Google Sheets
**Arquivo:** `app/database.py`
**Problema:** `update_campaign_stats()` faz múltiplas chamadas

```python
# Usar batch update
def update_campaign_stats(campaign_id: str, **updates):
    ws = get_worksheet('campaigns', fresh=True)
    # Preparar todas as atualizações
    cells_to_update = []
    for field, value in updates.items():
        # ... adiciona à lista

    # Uma única chamada API
    ws.update_cells(cells_to_update)
```

---

### Fase 2: Error Handling & Logging

#### 2.1 Logging Estruturado
**Novo arquivo:** `app/logger.py`

```python
import logging
from pathlib import Path

def setup_logger():
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("abaplay")

logger = setup_logger()
```

#### 2.2 Exceções Específicas
**Arquivos:** Todos os módulos
**Problema:** `except Exception: pass` engole erros

```python
# Antes
except Exception:
    pass

# Depois
except gspread.exceptions.APIError as e:
    logger.error(f"Erro na API do Google Sheets: {e}")
    raise
except ValueError as e:
    logger.warning(f"Valor inválido: {e}")
```

#### 2.3 Validação de Startup
**Arquivo:** `config/settings.py`

```python
def validate_config():
    """Valida configurações obrigatórias na inicialização"""
    errors = []

    if not RESEND_API_KEY:
        errors.append("RESEND_API_KEY não configurada")

    if not GOOGLE_SHEETS_SPREADSHEET_ID:
        errors.append("GOOGLE_SHEETS_SPREADSHEET_ID não configurada")

    if errors:
        raise ConfigurationError("\n".join(errors))

# Chamar no início do app
validate_config()
```

---

### Fase 3: Código & Manutenibilidade

#### 3.1 Helper para Extração de Email
**Arquivo:** `app/lead_processor.py`

```python
def get_lead_email(lead: dict) -> str:
    """Extrai email do lead independente da estrutura"""
    return (
        lead.get('contatos', {}).get('email_principal') or
        lead.get('email_principal') or
        ''
    )

def get_lead_phone(lead: dict) -> str:
    """Extrai telefone do lead"""
    return (
        lead.get('contatos', {}).get('telefone') or
        lead.get('telefone') or
        ''
    )
```

#### 3.2 Session State Simplificado
**Arquivo:** `app/main.py`

```python
DEFAULT_SESSION_STATE = {
    'campaign_id': None,
    'valid_leads': [],
    'discarded_leads': [],
    'sending_active': False,
    'emails_sent_session': 0,
    'current_lead_index': 0,
    'metadata': {},
    'use_llm': True,
    'llm_insights': {},
    'duplicate_leads': [],
    'approved_duplicates': [],
}

def init_session_state():
    for key, default in DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Carrega config persistente
    if 'daily_limit' not in st.session_state:
        config = load_user_config()
        st.session_state.daily_limit = config.get('daily_limit', DAILY_EMAIL_LIMIT)
```

#### 3.3 Constantes Centralizadas
**Arquivo:** `config/settings.py`

```python
# Timeouts
LLM_TIMEOUT_SECONDS = 30
API_RETRY_ATTEMPTS = 3
UI_FEEDBACK_DELAY = 2

# Cache TTLs
BLACKLIST_CACHE_TTL = 300  # 5 minutos
DAILY_COUNT_CACHE_TTL = 60  # 1 minuto

# UI
MAX_PREVIEW_LENGTH = 500
LEADS_PER_PAGE = 20
```

---

### Fase 4: Features & Negócio

#### 4.1 Retry Automático de Emails
**Arquivo:** `app/email_sender.py`

```python
import time
from functools import wraps

def with_retry(max_attempts=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (attempt + 1))  # Backoff
            return wrapper
    return decorator

@with_retry(max_attempts=3)
def send_email(lead, campaign_id, lead_id, use_llm=False):
    # ... implementação atual
```

#### 4.2 Persistir Score do LLM
**Arquivo:** `app/main.py` e `app/database.py`

```python
# Em database.py
def update_lead_score(lead_id: str, score: int, insights: str = None):
    ws = get_worksheet('leads', fresh=True)
    cell = ws.find(lead_id)
    if cell:
        row = cell.row
        ws.update_cell(row, SHEET_COLUMNS['leads'].index('score') + 1, score)

# Em main.py, após processamento LLM
for proc_lead in llm_result.get('leads_processados', []):
    if original and original.get('db_id'):
        update_lead_score(original['db_id'], proc_lead.get('score', 50))
```

---

## Melhorias Visuais (UI/UX)

### Design System

#### Paleta de Cores
```css
:root {
    /* Cores Primárias */
    --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --primary-500: #667eea;
    --primary-600: #5a67d8;
    --primary-700: #4c51bf;

    /* Cores de Status */
    --success-light: #c6f6d5;
    --success-dark: #22543d;
    --error-light: #fed7d7;
    --error-dark: #822727;
    --warning-light: #fefcbf;
    --warning-dark: #744210;
    --info-light: #bee3f8;
    --info-dark: #2a4365;

    /* Neutros */
    --gray-50: #f7fafc;
    --gray-100: #edf2f7;
    --gray-200: #e2e8f0;
    --gray-700: #4a5568;
    --gray-900: #1a202c;

    /* Sombras */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
    --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
}
```

### CSS Expandido
**Arquivo:** `app/main.py` (seção de CSS)

```css
/* === LAYOUT GERAL === */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* === HEADER === */
.app-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem;
    border-radius: 1rem;
    margin-bottom: 2rem;
    box-shadow: 0 10px 15px rgba(102, 126, 234, 0.2);
}

.app-header h1 {
    color: white;
    margin: 0;
    font-size: 2rem;
    font-weight: 700;
}

.app-header p {
    color: rgba(255,255,255,0.9);
    margin: 0.5rem 0 0 0;
}

/* === CARDS DE MÉTRICAS === */
.metric-card {
    background: white;
    border-radius: 1rem;
    padding: 1.5rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.07);
    border: 1px solid #e2e8f0;
    transition: transform 0.2s, box-shadow 0.2s;
}

.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 15px rgba(0,0,0,0.1);
}

.metric-card.primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
}

.metric-value {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1;
}

.metric-label {
    font-size: 0.875rem;
    color: #718096;
    margin-top: 0.5rem;
}

.metric-card.primary .metric-label {
    color: rgba(255,255,255,0.8);
}

/* === LEAD CARDS === */
.lead-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    padding: 1.25rem;
    margin: 0.75rem 0;
    transition: all 0.2s;
}

.lead-card:hover {
    border-color: #667eea;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.lead-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
}

.lead-name {
    font-weight: 600;
    font-size: 1.1rem;
    color: #1a202c;
}

.lead-location {
    color: #718096;
    font-size: 0.875rem;
}

/* === BADGES === */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

.badge-score {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.badge-score.high {
    background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
}

.badge-score.medium {
    background: linear-gradient(135deg, #ecc94b 0%, #d69e2e 100%);
}

.badge-score.low {
    background: linear-gradient(135deg, #fc8181 0%, #e53e3e 100%);
}

.badge-status {
    padding: 0.375rem 0.875rem;
}

.badge-status.sent {
    background: #c6f6d5;
    color: #22543d;
}

.badge-status.failed {
    background: #fed7d7;
    color: #822727;
}

.badge-status.pending {
    background: #fefcbf;
    color: #744210;
}

.badge-confianca {
    font-size: 0.7rem;
}

.badge-confianca.alta {
    background: #c6f6d5;
    color: #22543d;
}

.badge-confianca.media {
    background: #fefcbf;
    color: #744210;
}

.badge-confianca.baixa {
    background: #fed7d7;
    color: #822727;
}

/* === PROGRESS TRACKER === */
.progress-tracker {
    display: flex;
    justify-content: space-between;
    margin: 2rem 0;
    position: relative;
}

.progress-tracker::before {
    content: '';
    position: absolute;
    top: 1.25rem;
    left: 2rem;
    right: 2rem;
    height: 2px;
    background: #e2e8f0;
}

.progress-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    z-index: 1;
}

.progress-step-circle {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 50%;
    background: white;
    border: 2px solid #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    color: #718096;
}

.progress-step.active .progress-step-circle {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-color: #667eea;
    color: white;
}

.progress-step.completed .progress-step-circle {
    background: #48bb78;
    border-color: #48bb78;
    color: white;
}

.progress-step-label {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: #718096;
}

/* === TABS CUSTOMIZADOS === */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: #f7fafc;
    padding: 0.5rem;
    border-radius: 0.75rem;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 0.5rem;
    padding: 0.75rem 1.5rem;
    font-weight: 500;
}

.stTabs [aria-selected="true"] {
    background: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* === SIDEBAR === */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a202c 0%, #2d3748 100%);
}

section[data-testid="stSidebar"] .stMarkdown {
    color: #e2e8f0;
}

section[data-testid="stSidebar"] h2 {
    color: white;
    font-size: 1rem;
    border-bottom: 1px solid #4a5568;
    padding-bottom: 0.5rem;
}

/* === TABELAS === */
.dataframe {
    border: none !important;
    border-radius: 0.75rem;
    overflow: hidden;
}

.dataframe thead tr th {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    font-weight: 600;
    padding: 1rem !important;
}

.dataframe tbody tr:nth-child(even) {
    background: #f7fafc;
}

.dataframe tbody tr:hover {
    background: #edf2f7;
}

/* === BOTÕES === */
.stButton > button {
    border-radius: 0.5rem;
    font-weight: 500;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
}

.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* === INPUTS === */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    border-radius: 0.5rem;
    border: 2px solid #e2e8f0;
    transition: border-color 0.2s;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* === ALERTAS === */
.stAlert {
    border-radius: 0.75rem;
    border: none;
}

/* === EXPANDERS === */
.streamlit-expanderHeader {
    background: #f7fafc;
    border-radius: 0.5rem;
    font-weight: 500;
}

/* === ANIMAÇÕES === */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
    animation: fadeIn 0.3s ease-out;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.animate-pulse {
    animation: pulse 2s infinite;
}

/* === RESPONSIVIDADE === */
@media (max-width: 768px) {
    .metric-card {
        padding: 1rem;
    }

    .metric-value {
        font-size: 1.75rem;
    }

    .lead-card-header {
        flex-direction: column;
        gap: 0.5rem;
    }
}
```

### Componentes Visuais Novos

#### 1. Header com Gradiente
```python
def render_header():
    st.markdown("""
    <div class="app-header">
        <h1>📧 ABAplay Email Automation</h1>
        <p>Sistema inteligente de prospecção para clínicas ABA</p>
    </div>
    """, unsafe_allow_html=True)
```

#### 2. Cards de Métricas Estilizados
```python
def render_metric_cards():
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="metric-card primary">
            <div class="metric-value">28</div>
            <div class="metric-label">Emails Enviados</div>
        </div>
        """, unsafe_allow_html=True)
    # ... outros cards
```

#### 3. Progress Tracker para Envio
```python
def render_progress_tracker(current_step: int, total_steps: int):
    steps = ["Processando", "Gerando Email", "Enviando", "Concluído"]

    html = '<div class="progress-tracker">'
    for i, step in enumerate(steps):
        status = "completed" if i < current_step else "active" if i == current_step else ""
        icon = "✓" if i < current_step else str(i + 1)
        html += f'''
        <div class="progress-step {status}">
            <div class="progress-step-circle">{icon}</div>
            <div class="progress-step-label">{step}</div>
        </div>
        '''
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)
```

#### 4. Lead Cards Melhorados
```python
def render_lead_card(lead: dict, show_actions: bool = True):
    score = lead.get('score', 50)
    score_class = "high" if score >= 70 else "medium" if score >= 40 else "low"
    confianca = lead.get('confianca', 'media')

    st.markdown(f"""
    <div class="lead-card animate-fade-in">
        <div class="lead-card-header">
            <div>
                <div class="lead-name">{lead.get('nome_clinica', 'N/A')}</div>
                <div class="lead-location">📍 {lead.get('cidade_uf', 'N/A')}</div>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <span class="badge badge-score {score_class}">{score}</span>
                <span class="badge badge-confianca {confianca}">{confianca.upper()}</span>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.875rem; color: #4a5568;">
            <div>📧 {lead.get('contatos', {}).get('email_principal', 'N/A')}</div>
            <div>📞 {lead.get('contatos', {}).get('telefone', 'N/A')}</div>
            <div>👤 {lead.get('decisor', {}).get('nome', 'N/A')}</div>
            <div>💼 {lead.get('decisor', {}).get('cargo', 'N/A')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
```

#### 5. Status Badge para Emails
```python
def render_email_status_badge(status: str):
    return f'<span class="badge badge-status {status}">{status.upper()}</span>'
```

### Melhorias de UX

#### 1. Feedback Visual de Progresso
```python
def send_with_visual_feedback(lead, campaign_id, lead_id):
    progress_container = st.container()

    with progress_container:
        # Step 1
        render_progress_tracker(0, 4)
        status = st.empty()
        status.info("🔄 Preparando envio...")

        # Step 2
        time.sleep(0.5)
        render_progress_tracker(1, 4)
        status.info("🧠 Gerando email personalizado...")

        # Step 3
        render_progress_tracker(2, 4)
        status.info("📤 Enviando via Resend...")

        success, message, resend_id = send_email(lead, campaign_id, lead_id)

        # Step 4
        render_progress_tracker(3, 4)
        if success:
            status.success(f"✅ {message}")
        else:
            status.error(f"❌ {message}")
```

#### 2. Toast Notifications
```python
def show_toast(message: str, type: str = "info"):
    """Mostra notificação temporária"""
    if type == "success":
        st.toast(f"✅ {message}", icon="✅")
    elif type == "error":
        st.toast(f"❌ {message}", icon="❌")
    else:
        st.toast(f"ℹ️ {message}", icon="ℹ️")
```

#### 3. Skeleton Loading
```python
def render_skeleton_card():
    st.markdown("""
    <div class="lead-card animate-pulse">
        <div style="height: 1.5rem; background: #e2e8f0; border-radius: 0.25rem; width: 60%;"></div>
        <div style="height: 1rem; background: #e2e8f0; border-radius: 0.25rem; width: 40%; margin-top: 0.5rem;"></div>
        <div style="height: 1rem; background: #e2e8f0; border-radius: 0.25rem; width: 80%; margin-top: 1rem;"></div>
    </div>
    """, unsafe_allow_html=True)
```

---

## Cronograma de Implementação

### Semana 1: Performance & Estabilidade
| Dia | Tarefa | Prioridade |
|-----|--------|------------|
| 1 | Cache de blacklist | Crítico |
| 1 | Cache de contagem diária | Crítico |
| 2 | Timeout no LLM | Crítico |
| 2 | Batch updates Google Sheets | Alto |
| 3 | Otimizar detecção de duplicatas | Alto |
| 4 | Testes de performance | Alto |
| 5 | Buffer/ajustes | - |

### Semana 2: Error Handling & Logging
| Dia | Tarefa | Prioridade |
|-----|--------|------------|
| 1 | Criar módulo de logging | Alto |
| 2 | Substituir exceções silenciosas | Alto |
| 3 | Validação de startup | Alto |
| 4 | Feedback de erros ao usuário | Médio |
| 5 | Testes de robustez | - |

### Semana 3: UI/UX - Fase 1
| Dia | Tarefa | Prioridade |
|-----|--------|------------|
| 1 | Implementar novo CSS | Médio |
| 2 | Header e sidebar redesign | Médio |
| 3 | Cards de métricas | Médio |
| 4 | Lead cards melhorados | Médio |
| 5 | Progress tracker | Médio |

### Semana 4: UI/UX - Fase 2 & Código
| Dia | Tarefa | Prioridade |
|-----|--------|------------|
| 1 | Tabelas estilizadas | Médio |
| 2 | Feedback visual de envio | Médio |
| 3 | Helper functions (DRY) | Baixo |
| 4 | Type hints | Baixo |
| 5 | Documentação final | - |

---

## Checklist de Implementação

### Performance
- [x] Cache de blacklist com TTL (`app/cache.py`)
- [x] Cache de contagem diária (`app/cache.py`)
- [x] Timeout de 60s no LLM (`app/llm_processor.py`)
- [ ] Batch updates no Google Sheets
- [x] Carregar email_log uma vez para duplicatas (`app/database.py`)
- [ ] Cache no Data Viewer (session state)

### Error Handling
- [x] Módulo de logging (`app/logger.py`)
- [ ] Substituir `except Exception: pass`
- [x] Validação de configuração no startup (`config/settings.py`)
- [x] Feedback visual de erros (novos componentes UI)
- [ ] Sanitização de mensagens de erro

### Código
- [x] Helper `get_lead_email()` (`app/lead_processor.py`)
- [x] Helper `get_lead_phone()` (`app/lead_processor.py`)
- [x] Session state simplificado (`app/main.py`)
- [x] Constantes em `settings.py`
- [ ] Type hints nos módulos principais
- [ ] Docstrings completos

### UI/UX
- [x] CSS expandido com design system (`app/ui_components.py`)
- [x] Header com gradiente
- [x] Cards de métricas redesenhados
- [x] Lead cards com badges
- [x] Progress tracker para envio
- [x] Tabelas estilizadas
- [x] Skeleton loading
- [ ] Toast notifications
- [x] Sidebar dark theme
- [x] Tabs customizados
- [x] Animações sutis

### Features
- [x] Retry automático de emails (3 tentativas) (`app/email_sender.py`)
- [ ] Persistir score do LLM no banco
- [x] Invalidar cache após envio (via `update_email_status`)

---

## Arquivos a Criar/Modificar

### Novos Arquivos
```
app/logger.py          # Sistema de logging
app/ui_components.py   # Componentes visuais reutilizáveis
app/cache.py           # Gerenciamento de cache
```

### Arquivos a Modificar
```
app/main.py            # CSS + UI components
app/database.py        # Cache + batch updates
app/email_sender.py    # Retry logic
app/llm_processor.py   # Timeout
app/data_viewer.py     # Novo estilo
config/settings.py     # Constantes + validação
```

---

## Métricas de Sucesso

| Métrica | Antes | Meta |
|---------|-------|------|
| Chamadas API/100 leads | ~300 | ~50 |
| Tempo de carregamento | ~5s | ~1s |
| Erros silenciosos | Muitos | Zero |
| Cobertura de logs | 0% | 100% |
| Score de acessibilidade | - | >90 |

---

*Documento criado em 05/02/2026*
*Última atualização: 05/02/2026 - Implementação concluída*

---

## Resumo da Implementação

### Arquivos Criados
| Arquivo | Descrição |
|---------|-----------|
| `app/cache.py` | Sistema de cache com TTL para blacklist e contagem diária |
| `app/logger.py` | Sistema de logging estruturado com handlers |
| `app/ui_components.py` | Design system CSS + componentes visuais reutilizáveis |

### Arquivos Modificados
| Arquivo | Alterações |
|---------|------------|
| `app/main.py` | CSS integrado, componentes visuais, session state simplificado |
| `app/database.py` | Cache integrado, otimização de duplicatas |
| `app/email_sender.py` | Retry automático com backoff, helpers DRY |
| `app/lead_processor.py` | Helpers para extração de dados (email, phone, decisor) |
| `app/llm_processor.py` | Timeout com asyncio.wait_for() |
| `config/settings.py` | Constantes centralizadas, validação de configuração |
