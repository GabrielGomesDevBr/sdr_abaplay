"""
Validação de e-mails via Reoon API: verifica se a caixa de entrada realmente existe
antes de enviar, evitando bounces e preservando a reputação do domínio.

Custo: 1 crédito por verificação (20 créditos/dia no plano gratuito).

Pré-filtros locais (sem custo) eliminam domínios descartáveis e catch-all antes
de consumir créditos da API, reservando-os para e-mails corporativos.
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Dict, List, Tuple

from config.settings import REOON_API_KEY
from app.logger import log_info, log_warning, log_error


# Timeout por chamada individual à Reoon API
REOON_TIMEOUT = 7

# Timeout total para verificação de um lote de e-mails
REOON_BATCH_TIMEOUT = 60

# Workers paralelos para verificação em lote (3 = seguro para plano gratuito)
REOON_MAX_WORKERS = 3

# Domínios conhecidos que são catch-all ou não respondem com precisão
CATCH_ALL_DOMAINS = {
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "yahoo.com", "yahoo.com.br",
    "icloud.com", "me.com", "mac.com",
    "aol.com",
    "protonmail.com", "proton.me",
}

# Domínios de e-mail descartáveis/temporários conhecidos
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "temp-mail.org", "fakeinbox.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "dispostable.com", "yopmail.com", "trashmail.com",
    "maildrop.cc", "10minutemail.com", "getairmail.com", "mohmal.com",
    "tempail.com", "burnermail.io", "mailnesia.com", "tempmailo.com",
}


def is_disposable_email(email: str) -> bool:
    """Verifica se o e-mail usa um domínio descartável/temporário."""
    if not email or '@' not in email:
        return False
    domain = email.split('@')[1].lower()
    return domain in DISPOSABLE_DOMAINS


def is_catch_all_domain(email: str) -> bool:
    """Verifica se o domínio é catch-all (aceita qualquer endereço)."""
    if not email or '@' not in email:
        return False
    domain = email.split('@')[1].lower()
    return domain in CATCH_ALL_DOMAINS


def validate_email_smtp(email: str) -> Tuple[bool, str, str]:
    """
    Verifica se o endereço de e-mail existe via Reoon API.

    Retorna:
        Tuple[is_valid, status, message]
        - is_valid: True se o e-mail foi verificado como existente
        - status: 'valid' | 'invalid' | 'catch_all' | 'disposable' | 'unknown'
        - message: Descrição legível do resultado

    Status possíveis:
        - 'valid': API confirmou que o e-mail existe
        - 'invalid': API rejeitou o e-mail (caixa não existe)
        - 'catch_all': Domínio aceita qualquer endereço (não verificável)
        - 'disposable': E-mail de domínio descartável/temporário
        - 'unknown': Não foi possível verificar (sem API key, créditos esgotados, timeout)
    """
    if not email or '@' not in email:
        return False, 'invalid', 'E-mail vazio ou formato inválido'

    domain = email.split('@')[1].lower()

    # 1. Verifica domínios descartáveis (gratuito, sem créditos)
    if is_disposable_email(email):
        log_warning("email_validator", f"Disposable email detected: {email}")
        return False, 'disposable', f'Domínio descartável ({domain})'

    # 2. Verifica domínios catch-all conhecidos (gratuito, sem créditos)
    if is_catch_all_domain(email):
        log_info("email_validator", f"Catch-all domain, skipping API verify: {email}")
        return True, 'catch_all', f'Domínio catch-all ({domain}) — não verificável'

    # 3. Sem API key configurada — passa sem verificar
    if not REOON_API_KEY:
        log_warning("email_validator", "REOON_API_KEY not configured, skipping verification")
        return True, 'unknown', 'Verificação desativada (REOON_API_KEY não configurada)'

    # 4. Verificação via Reoon API (consome 1 crédito)
    try:
        log_info("email_validator", f"Reoon verify: {email}")
        response = requests.get(
            "https://emailverifier.reoon.com/api/v1/verify",
            params={"email": email, "key": REOON_API_KEY, "mode": "quick"},
            timeout=REOON_TIMEOUT
        )

        if response.status_code == 429:
            log_warning("email_validator", f"Reoon daily limit reached, passing: {email}")
            return True, 'unknown', 'Limite diário de verificações atingido'

        if response.status_code != 200:
            log_warning("email_validator", f"Reoon API error {response.status_code}: {email}")
            return True, 'unknown', f'Erro na API de verificação ({response.status_code})'

        data = response.json()
        status = data.get("status", "unknown")

        if status == "valid":
            log_info("email_validator", f"Reoon verified OK: {email}")
            return True, 'valid', 'E-mail verificado ✓ (Reoon)'
        elif status == "invalid":
            log_warning("email_validator", f"Reoon rejected: {email}")
            return False, 'invalid', 'E-mail rejeitado — caixa não existe'
        elif status == "disposable":
            log_warning("email_validator", f"Reoon disposable: {email}")
            return False, 'disposable', f'Domínio descartável ({domain})'
        elif status == "accept_all":
            log_info("email_validator", f"Reoon catch-all: {email}")
            return True, 'catch_all', f'Domínio catch-all ({domain}) — não verificável'
        else:
            log_warning("email_validator", f"Reoon unknown status '{status}': {email}")
            return True, 'unknown', f'Status de verificação inconclusivo ({status})'

    except requests.Timeout:
        log_warning("email_validator", f"Reoon timeout: {email}")
        return True, 'unknown', 'Timeout na verificação de e-mail'

    except Exception as e:
        log_error("email_validator", f"Reoon verify error: {email} — {e}", e)
        return True, 'unknown', f'Erro na verificação: {str(e)}'


def validate_email_smtp_batch(
    emails: List[str],
    max_workers: int = REOON_MAX_WORKERS,
    total_timeout: int = REOON_BATCH_TIMEOUT,
) -> Dict[str, Tuple[bool, str, str]]:
    """
    Verifica uma lista de e-mails em paralelo via Reoon API.

    Args:
        emails: Lista de endereços de e-mail a verificar
        max_workers: Número de verificações simultâneas
        total_timeout: Timeout total do lote em segundos

    Returns:
        Dict[email, Tuple[is_valid, status, message]]
        E-mails não verificados dentro do timeout retornam (True, 'unknown', ...)
    """
    results: Dict[str, Tuple[bool, str, str]] = {}

    if not emails:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(validate_email_smtp, email): email for email in emails}
        try:
            for future in as_completed(futures, timeout=total_timeout):
                email = futures[future]
                try:
                    results[email] = future.result()
                except Exception as e:
                    results[email] = (True, 'unknown', f'Erro: {str(e)}')
        except FuturesTimeoutError:
            # Timeout total do lote — emails restantes passam como unknown
            for future, email in futures.items():
                if email not in results:
                    future.cancel()
                    results[email] = (True, 'unknown', 'Timeout no lote de verificação')
            log_warning("email_validator", f"Batch timeout: {len(emails) - len(results)} emails não verificados")

    return results


def get_reoon_credits() -> Tuple[int, str]:
    """
    Retorna os créditos restantes na conta Reoon.

    Returns:
        Tuple[credits, error_message]
        - credits: número de créditos restantes, ou -1 em caso de erro
        - error_message: descrição do erro (vazia se OK)
    """
    if not REOON_API_KEY:
        return -1, "API key não configurada"
    try:
        response = requests.get(
            "https://emailverifier.reoon.com/api/v1/get-credits",
            params={"key": REOON_API_KEY},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return int(data.get("credits", 0)), ""
        return -1, f"Erro HTTP {response.status_code}"
    except Exception as e:
        return -1, str(e)
