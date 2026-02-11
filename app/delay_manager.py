"""
Sistema de delays inteligentes para evitar detecção de spam
"""
import random
from datetime import datetime, time
from typing import Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    DELAY_MEAN, DELAY_STD, DELAY_MIN,
    DELAY_BATCH_PAUSE, DELAY_BATCH_EXTRA_MIN, DELAY_BATCH_EXTRA_MAX,
    WORK_HOURS_START, WORK_HOURS_END, WORK_DAYS,
    DAILY_EMAIL_LIMIT
)
from app.database import get_emails_sent_today


def get_smart_delay(email_count: int = 0) -> float:
    """
    Gera delay que simula comportamento humano real usando distribuição gaussiana
    
    Args:
        email_count: Número de emails já enviados nesta sessão
        
    Returns:
        Delay em segundos
    """
    # Delay base com distribuição gaussiana
    base_delay = random.gauss(DELAY_MEAN, DELAY_STD)
    
    # Jitter de ±20% para variação adicional
    jitter = random.uniform(0.8, 1.2)
    delay = base_delay * jitter
    
    # Pausa maior a cada batch de emails (simula "ir ao banheiro")
    if email_count > 0 and email_count % DELAY_BATCH_PAUSE == 0:
        delay += random.uniform(DELAY_BATCH_EXTRA_MIN, DELAY_BATCH_EXTRA_MAX)
    
    # Garante delay mínimo
    return max(DELAY_MIN, delay)


def is_within_work_hours() -> Tuple[bool, str]:
    """
    Verifica se estamos dentro do horário comercial permitido
    
    Returns:
        Tuple[is_valid, message]
    """
    # Limitação de horário removida conforme solicitação
    return True, "Horário livre (restrição desativada)"


def can_send_email(daily_limit: int = DAILY_EMAIL_LIMIT) -> Tuple[bool, str]:
    """
    Verifica se podemos enviar mais emails hoje
    
    Args:
        daily_limit: Limite diário configurável (default: DAILY_EMAIL_LIMIT)
    
    Returns:
        Tuple[can_send, message]
    """
    # Verifica horário
    within_hours, hours_message = is_within_work_hours()
    if not within_hours:
        return False, hours_message
    
    # Verifica limite diário
    sent_today = get_emails_sent_today()
    if sent_today >= daily_limit:
        return False, f"Limite diário atingido: {sent_today}/{daily_limit} emails"
    
    remaining = daily_limit - sent_today
    return True, f"Pode enviar: {remaining} emails restantes hoje"


def get_remaining_emails_today(daily_limit: int = DAILY_EMAIL_LIMIT) -> int:
    """
    Retorna quantos emails ainda podem ser enviados hoje
    
    Args:
        daily_limit: Limite diário configurável (default: DAILY_EMAIL_LIMIT)
    """
    sent_today = get_emails_sent_today()
    return max(0, daily_limit - sent_today)


def estimate_completion_time(emails_pending: int, email_count: int = 0) -> str:
    """
    Estima tempo para completar o envio de emails pendentes
    
    Args:
        emails_pending: Número de emails na fila
        email_count: Número de emails já enviados nesta sessão
        
    Returns:
        String formatada com estimativa de tempo
    """
    if emails_pending == 0:
        return "Nenhum email pendente"
    
    # Calcula delays estimados
    total_seconds = 0
    for i in range(emails_pending):
        total_seconds += get_smart_delay(email_count + i)
    
    # Converte para formato legível
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    
    if hours > 0:
        return f"~{hours}h {minutes}min"
    else:
        return f"~{minutes}min"


def format_delay_for_display(delay_seconds: float) -> str:
    """Formata delay para exibição amigável"""
    minutes = int(delay_seconds // 60)
    seconds = int(delay_seconds % 60)
    
    if minutes > 0:
        return f"{minutes}min {seconds}s"
    else:
        return f"{seconds}s"


def get_next_available_time() -> datetime:
    """Retorna próximo horário disponível para envio"""
    # Como não há mais restrição de horário, o próximo horário é agora
    return datetime.now()
