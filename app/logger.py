"""
Sistema de logging estruturado para a aplicação.
Centraliza toda a configuração de logs.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# Diretório de logs
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Formato de log
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "abaplay",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Configura e retorna um logger.

    Args:
        name: Nome do logger
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Se True, salva logs em arquivo
        log_to_console: Se True, mostra logs no console

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)

    # Evita duplicação de handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    # Handler para arquivo
    if log_to_file:
        log_file = LOG_DIR / f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Handler para console
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Logger principal da aplicação
logger = setup_logger("abaplay", log_to_console=False)

# Loggers específicos por módulo
db_logger = setup_logger("abaplay.database", log_to_console=False)
email_logger = setup_logger("abaplay.email", log_to_console=False)
llm_logger = setup_logger("abaplay.llm", log_to_console=False)
gemini_logger = setup_logger("abaplay.gemini", log_to_console=False)
ui_logger = setup_logger("abaplay.ui", log_to_console=False)


def log_error(module: str, message: str, exception: Optional[Exception] = None):
    """
    Log de erro com contexto.

    Args:
        module: Nome do módulo (database, email, llm, ui)
        message: Mensagem de erro
        exception: Exceção opcional para incluir traceback
    """
    module_logger = {
        "database": db_logger,
        "email": email_logger,
        "llm": llm_logger,
        "gemini": gemini_logger,
        "ui": ui_logger
    }.get(module, logger)

    if exception:
        module_logger.error(f"{message}: {exception}", exc_info=True)
    else:
        module_logger.error(message)


def log_warning(module: str, message: str):
    """Log de warning."""
    module_logger = {
        "database": db_logger,
        "email": email_logger,
        "llm": llm_logger,
        "gemini": gemini_logger,
        "ui": ui_logger
    }.get(module, logger)

    module_logger.warning(message)


def log_info(module: str, message: str):
    """Log de informação."""
    module_logger = {
        "database": db_logger,
        "email": email_logger,
        "llm": llm_logger,
        "gemini": gemini_logger,
        "ui": ui_logger
    }.get(module, logger)

    module_logger.info(message)


def log_debug(module: str, message: str):
    """Log de debug."""
    module_logger = {
        "database": db_logger,
        "email": email_logger,
        "llm": llm_logger,
        "gemini": gemini_logger,
        "ui": ui_logger
    }.get(module, logger)

    module_logger.debug(message)


def log_email_sent(email_to: str, subject: str, resend_id: str):
    """Log específico para email enviado."""
    email_logger.info(f"EMAIL_SENT | to={email_to} | subject={subject[:50]}... | resend_id={resend_id}")


def log_email_failed(email_to: str, subject: str, error: str):
    """Log específico para email que falhou."""
    email_logger.error(f"EMAIL_FAILED | to={email_to} | subject={subject[:50]}... | error={error}")


def log_api_call(service: str, endpoint: str, success: bool, duration_ms: Optional[float] = None):
    """Log de chamada à API externa."""
    status = "SUCCESS" if success else "FAILED"
    duration = f" | duration={duration_ms:.0f}ms" if duration_ms else ""
    logger.info(f"API_CALL | service={service} | endpoint={endpoint} | status={status}{duration}")


def log_cache_hit(cache_type: str, key: str):
    """Log de cache hit."""
    logger.debug(f"CACHE_HIT | type={cache_type} | key={key}")


def log_cache_miss(cache_type: str, key: str):
    """Log de cache miss."""
    logger.debug(f"CACHE_MISS | type={cache_type} | key={key}")
