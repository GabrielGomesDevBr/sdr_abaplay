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

# === Gemini Configuration ===
GEMINI_API_KEY = _get_secret("GEMINI_API_KEY", "")
GEMINI_MODEL = _get_secret("GEMINI_MODEL", "gemini-2.5-flash")

# Modelos Gemini disponíveis para seleção na UI
GEMINI_MODELS = {
    "gemini-2.5-flash": "2.5 Flash (rápido, 1500 req/dia grátis)",
    "gemini-2.5-flash-lite": "2.5 Flash-Lite (ultra rápido, 1500 req/dia grátis)",
    "gemini-2.5-pro": "2.5 Pro (raciocínio avançado, 50 req/dia grátis)",
    "gemini-3-pro-preview": "3.0 Pro (mais capaz, requer créditos)",
    "gemini-3-flash-preview": "3.0 Flash (rápido, requer créditos)",
}

# === Database Configuration ===
DATABASE_URL = _get_secret("DATABASE_URL", "")

# === Google Sheets Configuration (mantido para migração) ===
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
        'assunto': '{nome_decisor}, relatórios às 22h na {nome_clinica}?',
        'corpo': '''
Oi {nome_decisor},

Sei que quem lidera uma clínica ABA em {cidade} conhece bem a rotina: terapeutas terminando relatórios em casa, PEI que consome o fim de semana, e a sensação de que a burocracia está roubando tempo das crianças.

Construímos o ABAplay porque somos analistas do comportamento — cansados de softwares feitos por quem nunca aplicou sessão no chão. Hoje, clínicas nos dizem que recuperaram as noites.

Posso te mostrar em 15 minutos?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
        '''
    },
    'sem_decisor': {
        'assunto': '{nome_clinica}: quanto tempo sua equipe perde com burocracia?',
        'corpo': '''
Oi, equipe {nome_clinica}!

Clínicas ABA vivem um paradoxo: quanto mais pacientes atendem, mais tempo perdem com relatórios, PEI e documentação — e menos tempo sobra para as crianças.

Somos analistas do comportamento que construíram o ABAplay justamente para devolver esse tempo. Clínicas que usam nos dizem que recuperaram noites e fins de semana.

Posso mostrar como funciona em 15 minutos?

---
Gabriel Gomes
ABAplay | Gestão para Clínicas ABA
(11) 98854-3437
abaplay.app.br/info

Responda REMOVER para sair da lista.
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

    if not DATABASE_URL:
        errors.append("DATABASE_URL não configurada no .env")

    # Verifica formato da API key do Resend
    if RESEND_API_KEY and not RESEND_API_KEY.startswith('re_'):
        errors.append("RESEND_API_KEY com formato inválido (deve começar com 're_')")

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
        'database_url': bool(DATABASE_URL),
        'gemini_api_key': bool(GEMINI_API_KEY),
        'daily_limit': DAILY_EMAIL_LIMIT,
        'work_hours': f"{WORK_HOURS_START}h - {WORK_HOURS_END}h",
        'delay_mean': DELAY_MEAN,
    }
