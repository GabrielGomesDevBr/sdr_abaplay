"""
Sistema de cache em memória para otimização de performance.
Reduz chamadas à API do Google Sheets.
"""
import time
from typing import Any, Optional, Set, Dict
from datetime import datetime
from threading import Lock


class CacheEntry:
    """Entrada de cache com TTL"""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = time.time() + ttl
        self.created_at = time.time()

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class MemoryCache:
    """Cache em memória thread-safe com TTL"""

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retorna valor do cache ou None se expirado/inexistente"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl: int = 300):
        """Define valor no cache com TTL em segundos"""
        with self._lock:
            self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str):
        """Remove entrada do cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()

    def invalidate_pattern(self, pattern: str):
        """Invalida todas as chaves que começam com o pattern"""
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]


# Instância global do cache
_cache = MemoryCache()


# === Cache de Blacklist ===

_blacklist_cache: Set[str] = set()
_blacklist_cache_time: float = 0
BLACKLIST_CACHE_TTL = 300  # 5 minutos


def get_blacklist_cache() -> Set[str]:
    """Retorna cache da blacklist"""
    global _blacklist_cache, _blacklist_cache_time

    if time.time() - _blacklist_cache_time > BLACKLIST_CACHE_TTL:
        return set()  # Cache expirado, forçar refresh

    return _blacklist_cache


def set_blacklist_cache(emails: Set[str]):
    """Atualiza cache da blacklist"""
    global _blacklist_cache, _blacklist_cache_time

    _blacklist_cache = emails
    _blacklist_cache_time = time.time()


def is_blacklist_cache_valid() -> bool:
    """Verifica se cache da blacklist ainda é válido"""
    global _blacklist_cache_time

    return time.time() - _blacklist_cache_time <= BLACKLIST_CACHE_TTL


def invalidate_blacklist_cache():
    """Invalida cache da blacklist"""
    global _blacklist_cache, _blacklist_cache_time

    _blacklist_cache = set()
    _blacklist_cache_time = 0


# === Cache de Contagem Diária ===

_daily_count_cache: Dict[str, int] = {}
_daily_count_cache_time: float = 0
DAILY_COUNT_CACHE_TTL = 60  # 1 minuto


def get_daily_count_cache() -> Optional[int]:
    """Retorna contagem diária do cache ou None se expirado"""
    global _daily_count_cache, _daily_count_cache_time

    today = datetime.now().strftime('%Y-%m-%d')

    # Cache expirado ou de outro dia
    if time.time() - _daily_count_cache_time > DAILY_COUNT_CACHE_TTL:
        return None

    return _daily_count_cache.get(today)


def set_daily_count_cache(count: int):
    """Atualiza cache da contagem diária"""
    global _daily_count_cache, _daily_count_cache_time

    today = datetime.now().strftime('%Y-%m-%d')
    _daily_count_cache = {today: count}
    _daily_count_cache_time = time.time()


def increment_daily_count_cache():
    """Incrementa contagem diária no cache (após envio bem-sucedido)"""
    global _daily_count_cache, _daily_count_cache_time

    today = datetime.now().strftime('%Y-%m-%d')

    if today in _daily_count_cache:
        _daily_count_cache[today] += 1
        _daily_count_cache_time = time.time()


def invalidate_daily_count_cache():
    """Invalida cache da contagem diária"""
    global _daily_count_cache, _daily_count_cache_time

    _daily_count_cache = {}
    _daily_count_cache_time = 0


# === Cache Genérico ===

def cache_get(key: str) -> Optional[Any]:
    """Wrapper para cache genérico"""
    return _cache.get(key)


def cache_set(key: str, value: Any, ttl: int = 300):
    """Wrapper para cache genérico"""
    _cache.set(key, value, ttl)


def cache_delete(key: str):
    """Wrapper para cache genérico"""
    _cache.delete(key)


def cache_clear():
    """Limpa todos os caches"""
    _cache.clear()
    invalidate_blacklist_cache()
    invalidate_daily_count_cache()
