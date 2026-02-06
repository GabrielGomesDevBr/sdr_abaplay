"""
Configurações centralizadas do sistema de automação de emails ABAplay
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Busca secret do Streamlit ou .env"""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


# === API Configuration ===
RESEND_API_KEY = _get_secret("RESEND_API_KEY", "")
SENDER_EMAIL = _get_secret("SENDER_EMAIL", "")
SENDER_NAME = _get_secret("SENDER_NAME", "ABAplay")

# === Email Limits ===
DAILY_EMAIL_LIMIT = 20  # Limite padrão para envios diários
MAX_ATTEMPTS_PER_LEAD = 2  # Máximo de tentativas por lead

# === Schedule ===
WORK_HOURS_START = 9   # 09:00
WORK_HOURS_END = 18    # 18:00
WORK_DAYS = [0, 1, 2, 3, 4]  # Segunda a Sexta (0=Monday)

# === Delay Configuration (seconds) ===
DELAY_MEAN = 90        # Média do delay gaussiano
DELAY_STD = 30         # Desvio padrão
DELAY_MIN = 45         # Delay mínimo
DELAY_BATCH_PAUSE = 5  # Pausa maior a cada N emails
DELAY_BATCH_EXTRA_MIN = 300   # 5 min extras a cada batch
DELAY_BATCH_EXTRA_MAX = 600   # 10 min extras a cada batch

# === Paths ===
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DESKTOP_PATH = Path(os.getenv("DESKTOP_PATH", Path.home() / "Área de Trabalho"))

# === Google Sheets Configuration ===
GOOGLE_SHEETS_SPREADSHEET_ID = _get_secret("GOOGLE_SHEETS_SPREADSHEET_ID", "")
GOOGLE_SHEETS_CREDENTIALS_PATH = _get_secret("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json")

# === Lead Scoring Weights ===
SCORE_EMAIL_EXISTS = 30
SCORE_EMAIL_TYPE = {
    'nominal': 25,    # secretariadraflaviana@gmail.com
    'cargo': 20,      # diretoria@clinica.com
    'generico': 10,   # contato@clinica.com
    'form_only': 0    # Sem email
}
SCORE_CONFIDENCE = {
    'alta': 25,
    'media': 15,
    'baixa': 5
}
SCORE_DECISOR_IDENTIFIED = 10
SCORE_HAS_WEBSITE = 10

# === Email Templates ===
TEMPLATES = {
    'decisor_identificado': {
        'assunto': '{nome_decisor}, como {nome_clinica} pode economizar 15h/semana em PEI',
        'corpo': '''
Olá {nome_decisor},

Vi que você lidera a {nome_clinica} em {cidade}. 

Sei que relatórios de evolução e PEI consomem tempo precioso da sua equipe. O ABAplay automatiza essa documentação:

✅ PEI escolar gerado em 5 minutos (100% LBI/BNCC)
✅ Relatórios de evolução com 1 clique
✅ Documentação "blindada" contra glosas de convênio

Clínicas ABA perdem em média 5-8% da receita por glosas. Posso mostrar como evitar isso em 15 minutos?

Ofereço 7 dias grátis para você testar com sua equipe.

---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com "REMOVER".
        '''
    },
    'sem_decisor': {
        'assunto': '{nome_clinica}: reduzir glosas em até 8% com documentação padronizada',
        'corpo': '''
Olá equipe {nome_clinica},

Clínicas ABA perdem em média 5-8% da receita por glosas de convênio. Documentação inadequada é a principal causa.

O ABAplay resolve isso com:

✅ +2.400 programas ABA baseados em evidências
✅ PEI escolar gerado em 5 minutos
✅ Relatórios padronizados que auditores adoram
✅ Portal para pais acompanharem em tempo real

Podemos agendar 15 minutos para eu mostrar como funciona?

Oferecemos 7 dias grátis, sem cartão de crédito.

---
Gabriel Gomes
Engenheiro de Software | ABAplay
(11) 98854-3437
https://abaplay.app.br/info

Se não deseja receber mais emails, responda com "REMOVER".
        '''
    }
}

# === Unsubscribe ===
UNSUBSCRIBE_KEYWORDS = ['remover', 'unsubscribe', 'descadastrar', 'não quero', 'pare']

# === Timeouts ===
LLM_TIMEOUT_SECONDS = 60  # Timeout para processamento de leads
LLM_EMAIL_TIMEOUT_SECONDS = 30  # Timeout para geração de email
API_RETRY_ATTEMPTS = 3

# === Cache TTLs (segundos) ===
BLACKLIST_CACHE_TTL = 300  # 5 minutos
DAILY_COUNT_CACHE_TTL = 60  # 1 minuto

# === UI Constants ===
UI_FEEDBACK_DELAY = 2  # Segundos para feedback visual
MAX_PREVIEW_LENGTH = 500  # Caracteres no preview
LEADS_PER_PAGE = 20


class ConfigurationError(Exception):
    """Erro de configuração da aplicação"""
    pass


def validate_config() -> list:
    """
    Valida configurações obrigatórias.

    Returns:
        Lista de erros (vazia se tudo OK)
    """
    errors = []

    # Verifica API keys obrigatórias
    if not RESEND_API_KEY:
        errors.append("RESEND_API_KEY não configurada no .env")

    if not SENDER_EMAIL:
        errors.append("SENDER_EMAIL não configurado no .env")

    if not GOOGLE_SHEETS_SPREADSHEET_ID:
        errors.append("GOOGLE_SHEETS_SPREADSHEET_ID não configurado no .env")

    # Verifica formato da API key do Resend
    if RESEND_API_KEY and not RESEND_API_KEY.startswith('re_'):
        errors.append("RESEND_API_KEY com formato inválido (deve começar com 're_')")

    # Verifica se credenciais do Google existem
    creds_path = Path(GOOGLE_SHEETS_CREDENTIALS_PATH)
    if not creds_path.is_absolute():
        creds_path = BASE_DIR / GOOGLE_SHEETS_CREDENTIALS_PATH

    if not creds_path.exists():
        # Verifica se há credenciais no Streamlit secrets ou env
        import os
        if not os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"):
            try:
                import streamlit as st
                if "GOOGLE_SHEETS_CREDENTIALS" not in st.secrets:
                    errors.append(f"Credenciais do Google não encontradas em {creds_path}")
            except:
                errors.append(f"Credenciais do Google não encontradas em {creds_path}")

    return errors


def get_config_status() -> dict:
    """
    Retorna status das configurações para exibição.

    Returns:
        Dict com status de cada configuração
    """
    return {
        'resend_api_key': bool(RESEND_API_KEY),
        'sender_email': bool(SENDER_EMAIL),
        'google_sheets_id': bool(GOOGLE_SHEETS_SPREADSHEET_ID),
        'daily_limit': DAILY_EMAIL_LIMIT,
        'work_hours': f"{WORK_HOURS_START}h - {WORK_HOURS_END}h",
        'delay_mean': DELAY_MEAN,
    }
