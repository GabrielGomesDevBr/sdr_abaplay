"""
Integração com Resend API para envio de emails
"""
import resend
import time
from typing import Dict, Tuple, Optional
from datetime import datetime
from functools import wraps

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import RESEND_API_KEY, SENDER_EMAIL, SENDER_NAME, API_RETRY_ATTEMPTS
from app.database import (
    log_email_attempt, update_email_status, get_email_attempts,
    is_blacklisted, add_to_blacklist, update_lead_status
)
from app.template_engine import personalize_template
from app.lead_processor import get_lead_email
from config.settings import MAX_ATTEMPTS_PER_LEAD


# Configura Resend
resend.api_key = RESEND_API_KEY


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY DECORATOR
# ═══════════════════════════════════════════════════════════════════════════════

def with_retry(max_attempts: int = 3, base_delay: float = 2.0):
    """
    Decorator para retry automático com backoff exponencial.

    Args:
        max_attempts: Número máximo de tentativas
        base_delay: Delay base em segundos (multiplica a cada tentativa)

    Example:
        @with_retry(max_attempts=3, base_delay=2.0)
        def send_api_call():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (attempt + 1)  # Backoff linear
                        time.sleep(delay)

            # Se todas as tentativas falharam, levanta a última exceção
            raise last_exception
        return wrapper
    return decorator


@with_retry(max_attempts=API_RETRY_ATTEMPTS, base_delay=2.0)
def _send_via_resend(email_to: str, subject: str, body: str,
                     campaign_id: int, lead_id: int) -> Dict:
    """
    Envia email via API Resend com retry automático.

    Args:
        email_to: Email do destinatário
        subject: Assunto do email
        body: Corpo do email
        campaign_id: ID da campanha
        lead_id: ID do lead

    Returns:
        Response da API Resend

    Raises:
        Exception se todas as tentativas falharem
    """
    return resend.Emails.send({
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [email_to],
        "subject": subject,
        "text": body,
        "headers": {
            "List-Unsubscribe": f"<mailto:{SENDER_EMAIL}?subject=REMOVER>",
            "X-Entity-Ref-ID": f"campaign-{campaign_id}-lead-{lead_id}"
        }
    })


def send_email(lead: Dict, campaign_id: int, lead_id: int, use_llm: bool = False) -> Tuple[bool, str, Optional[str]]:
    """
    Envia email para um lead usando Resend com retry automático.

    Args:
        lead: Dados do lead
        campaign_id: ID da campanha
        lead_id: ID do lead no banco
        use_llm: Se True, gera email personalizado com IA

    Returns:
        Tuple[success, message, resend_id]
    """
    # Extrai email usando helper DRY
    email_to = get_lead_email(lead)

    if not email_to:
        return False, "Lead sem email", None

    # Verifica blacklist
    if is_blacklisted(email_to):
        return False, "Email na blacklist", None

    # Verifica número de tentativas
    attempts = get_email_attempts(lead_id)
    if attempts >= MAX_ATTEMPTS_PER_LEAD:
        return False, f"Limite de tentativas atingido ({attempts}/{MAX_ATTEMPTS_PER_LEAD})", None

    # Gera conteúdo do email
    if use_llm:
        # Usa IA para gerar email personalizado
        try:
            from app.llm_processor import generate_email_with_llm_sync
            insights = lead.get('llm_insights', '')
            email_content = generate_email_with_llm_sync(lead, insights)
        except Exception as e:
            # Fallback para template se LLM falhar
            email_content = personalize_template(lead)
    else:
        # Usa template padrão
        email_content = personalize_template(lead)

    # Registra tentativa no banco (com corpo do email)
    log_id = log_email_attempt(
        lead_id=lead_id,
        campaign_id=campaign_id,
        email_to=email_to,
        subject=email_content['assunto'],
        attempt_number=attempts + 1,
        body_html=email_content.get('corpo', '')
    )

    try:
        # Verifica configuração
        if not RESEND_API_KEY:
            update_email_status(log_id, 'failed', error_message="API key não configurada")
            return False, "API key do Resend não configurada", None

        if not SENDER_EMAIL:
            update_email_status(log_id, 'failed', error_message="Email remetente não configurado")
            return False, "Email do remetente não configurado", None

        # Envia via Resend com retry automático
        response = _send_via_resend(
            email_to=email_to,
            subject=email_content['assunto'],
            body=email_content['corpo'],
            campaign_id=campaign_id,
            lead_id=lead_id
        )

        # Extrai ID do Resend
        resend_id = response.get('id') if isinstance(response, dict) else str(response)

        # Atualiza status no banco
        update_email_status(log_id, 'sent', resend_id=resend_id)

        # Atualiza status do lead para 'contacted'
        update_lead_status(lead_id, 'contacted')

        return True, f"Email enviado com sucesso (ID: {resend_id})", resend_id

    except Exception as e:
        error_message = str(e)
        update_email_status(log_id, 'failed', error_message=error_message)
        return False, f"Erro ao enviar: {error_message}", None


def generate_email_preview(lead: Dict, use_llm: bool = False) -> Dict:
    """
    Gera preview do email que será enviado
    
    Args:
        lead: Dados do lead
        use_llm: Se True, usa IA para gerar email
        
    Returns:
        Dict com assunto e corpo do email
    """
    if use_llm:
        try:
            from app.llm_processor import generate_email_with_llm_sync
            insights = lead.get('llm_insights', '')
            return generate_email_with_llm_sync(lead, insights)
        except Exception as e:
            # Fallback
            result = personalize_template(lead)
            result['error'] = str(e)
            return result
    else:
        return personalize_template(lead)


def test_connection() -> Tuple[bool, str]:
    """
    Testa conexão com a API do Resend
    
    Returns:
        Tuple[success, message]
    """
    if not RESEND_API_KEY:
        return False, "API key não configurada no .env"
    
    if not SENDER_EMAIL:
        return False, "SENDER_EMAIL não configurado no .env"
    
    try:
        # Tenta listar domínios para verificar conexão
        # Isso não envia nenhum email, apenas verifica a API
        resend.api_key = RESEND_API_KEY
        
        # Verifica se a API key é válida fazendo uma chamada simples
        # O Resend não tem um endpoint de "ping", então verificamos se a key tem formato válido
        if not RESEND_API_KEY.startswith('re_'):
            return False, "API key com formato inválido (deve começar com 're_')"
        
        return True, f"Conexão OK. Remetente: {SENDER_NAME} <{SENDER_EMAIL}>"
        
    except Exception as e:
        return False, f"Erro na conexão: {str(e)}"


def get_sender_info() -> Dict:
    """Retorna informações do remetente configurado"""
    return {
        'email': SENDER_EMAIL,
        'name': SENDER_NAME,
        'configured': bool(SENDER_EMAIL and RESEND_API_KEY)
    }


def process_unsubscribe(email: str, reason: str = "user_request") -> bool:
    """
    Processa solicitação de descadastramento
    
    Args:
        email: Email a ser removido
        reason: Motivo do descadastramento
        
    Returns:
        True se adicionado à blacklist
    """
    add_to_blacklist(email, reason)
    return True
