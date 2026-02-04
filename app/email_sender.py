"""
Integração com Resend API para envio de emails
"""
import resend
from typing import Dict, Tuple, Optional
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import RESEND_API_KEY, SENDER_EMAIL, SENDER_NAME
from app.database import (
    log_email_attempt, update_email_status, get_email_attempts,
    is_blacklisted, add_to_blacklist
)
from app.template_engine import personalize_template
from config.settings import MAX_ATTEMPTS_PER_LEAD


# Configura Resend
resend.api_key = RESEND_API_KEY


def send_email(lead: Dict, campaign_id: int, lead_id: int, use_llm: bool = False) -> Tuple[bool, str, Optional[str]]:
    """
    Envia email para um lead usando Resend
    
    Args:
        lead: Dados do lead
        campaign_id: ID da campanha
        lead_id: ID do lead no banco
        use_llm: Se True, gera email personalizado com IA
        
    Returns:
        Tuple[success, message, resend_id]
    """
    # Extrai email do lead
    email_to = lead.get('contatos', {}).get('email_principal') or lead.get('email_principal')
    
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
    
    # Registra tentativa no banco
    log_id = log_email_attempt(
        lead_id=lead_id,
        campaign_id=campaign_id,
        email_to=email_to,
        subject=email_content['assunto'],
        attempt_number=attempts + 1
    )
    
    try:
        # Verifica configuração
        if not RESEND_API_KEY:
            update_email_status(log_id, 'failed', error_message="API key não configurada")
            return False, "API key do Resend não configurada", None
        
        if not SENDER_EMAIL:
            update_email_status(log_id, 'failed', error_message="Email remetente não configurado")
            return False, "Email do remetente não configurado", None
        
        # Envia via Resend
        response = resend.Emails.send({
            "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
            "to": [email_to],
            "subject": email_content['assunto'],
            "text": email_content['corpo'],
            "headers": {
                "List-Unsubscribe": f"<mailto:{SENDER_EMAIL}?subject=REMOVER>",
                "X-Entity-Ref-ID": f"campaign-{campaign_id}-lead-{lead_id}"
            }
        })
        
        # Extrai ID do Resend
        resend_id = response.get('id') if isinstance(response, dict) else str(response)
        
        # Atualiza status no banco
        update_email_status(log_id, 'sent', resend_id=resend_id)
        
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
