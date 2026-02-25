"""
Gerenciamento de banco de dados usando Neon PostgreSQL para automação de emails.

Mantém a mesma interface pública da versão anterior (Google Sheets),
substituindo apenas o backend por psycopg2.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import uuid
import os

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATABASE_URL
from app.cache import (
    get_blacklist_cache, set_blacklist_cache, is_blacklist_cache_valid,
    invalidate_blacklist_cache, get_daily_count_cache, set_daily_count_cache,
    increment_daily_count_cache, invalidate_daily_count_cache
)


# === PostgreSQL Connection ===

_connection = None


def get_connection():
    """Retorna conexão reutilizável (reconecta se necessário)"""
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg2.connect(DATABASE_URL)
        _connection.autocommit = True
        with _connection.cursor() as cur:
            cur.execute("SET search_path TO sdr")
    return _connection


@contextmanager
def get_cursor():
    """Context manager para cursor com RealDictCursor"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
    except psycopg2.InterfaceError:
        # Conexão perdida, reconecta
        global _connection
        _connection = None
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
    finally:
        cur.close()


def _generate_id() -> str:
    """Gera um ID único"""
    return str(uuid.uuid4())[:8]


def _now_iso() -> str:
    """Retorna timestamp atual em formato ISO"""
    return datetime.now().isoformat()


def _row_to_dict(row) -> Dict:
    """Converte RealDictRow para dict normal com timestamps como string"""
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif v is None:
            d[k] = ''
    # Garante que campos numéricos sejam int
    for field in ['score', 'total_leads', 'emails_sent', 'emails_failed', 'attempt_number']:
        if field in d:
            try:
                d[field] = int(d[field]) if d[field] else 0
            except (ValueError, TypeError):
                d[field] = 0
    return d


def init_database():
    """Verifica conexão com o banco (as tabelas já existem no Neon)"""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
    except Exception as e:
        print(f"[WARN] Erro ao conectar ao banco: {e}")


# === Campaign Functions ===

def create_campaign(name: str, region: str = None) -> str:
    """Cria nova campanha e retorna o ID"""
    campaign_id = _generate_id()
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO campaigns (id, name, region, created_at, updated_at, status, total_leads, emails_sent, emails_failed)
            VALUES (%s, %s, %s, NOW(), NOW(), 'pending', 0, 0, 0)
        """, (campaign_id, name, region or ''))
    return campaign_id


def update_campaign_stats(campaign_id: str, total_leads: int = None,
                          emails_sent: int = None, emails_failed: int = None,
                          status: str = None):
    """Atualiza estatísticas da campanha"""
    try:
        updates = []
        params = []

        if total_leads is not None:
            updates.append("total_leads = %s")
            params.append(total_leads)
        if emails_sent is not None:
            updates.append("emails_sent = %s")
            params.append(emails_sent)
        if emails_failed is not None:
            updates.append("emails_failed = %s")
            params.append(emails_failed)
        if status is not None:
            updates.append("status = %s")
            params.append(status)

        if not updates:
            return

        updates.append("updated_at = NOW()")
        params.append(campaign_id)

        with get_cursor() as cur:
            cur.execute(
                f"UPDATE campaigns SET {', '.join(updates)} WHERE id = %s",
                params
            )
    except Exception:
        pass


def get_campaign(campaign_id: str) -> Optional[Dict]:
    """Retorna dados da campanha"""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


# === Lead Functions ===

def insert_lead(campaign_id: str, lead_data: Dict) -> str:
    """Insere um lead e retorna o ID"""
    lead_id = _generate_id()
    contexto = lead_data.get('contexto_abordagem', {})

    # Score com validação 0-100
    score = lead_data.get('score', 0)
    try:
        score = max(0, min(100, int(score)))
    except (ValueError, TypeError):
        score = 0

    # Confiança com validação
    confianca = lead_data.get('confianca', '')
    if confianca not in ('', 'alta', 'media', 'baixa'):
        confianca = ''

    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO leads (
                id, campaign_id, status, nome_clinica, endereco, cidade_uf, cnpj, site,
                decisor_nome, decisor_cargo, decisor_linkedin, email_principal, email_tipo,
                telefone, whatsapp, instagram, fonte, confianca, score,
                resumo_clinica, perfil_decisor, gancho_personalizacao, dor_provavel, tom_sugerido,
                notas, motivo_descarte, raw_data, created_at, updated_at
            ) VALUES (
                %s, %s, 'new', %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                '', '', %s, NOW(), NOW()
            )
        """, (
            lead_id,
            campaign_id,
            lead_data.get('nome_clinica', ''),
            lead_data.get('endereco', ''),
            lead_data.get('cidade_uf', ''),
            lead_data.get('cnpj', ''),
            lead_data.get('site', ''),
            lead_data.get('decisor', {}).get('nome', ''),
            lead_data.get('decisor', {}).get('cargo', ''),
            lead_data.get('decisor', {}).get('linkedin', ''),
            lead_data.get('contatos', {}).get('email_principal', ''),
            lead_data.get('contatos', {}).get('email_tipo', ''),
            lead_data.get('contatos', {}).get('telefone', ''),
            lead_data.get('contatos', {}).get('whatsapp', ''),
            lead_data.get('contatos', {}).get('instagram', ''),
            lead_data.get('fonte', ''),
            confianca,
            score,
            contexto.get('resumo_clinica', ''),
            contexto.get('perfil_decisor', ''),
            contexto.get('gancho_personalizacao', ''),
            contexto.get('dor_provavel', ''),
            contexto.get('tom_sugerido', ''),
            json.dumps(lead_data),
        ))
    return lead_id


def update_lead_score(lead_id: str, score: int):
    """Atualiza o score de um lead"""
    try:
        score = max(0, min(100, int(score)))
        with get_cursor() as cur:
            cur.execute(
                "UPDATE leads SET score = %s, updated_at = NOW() WHERE id = %s",
                (score, lead_id)
            )
    except Exception:
        pass


def get_leads_by_campaign(campaign_id: str, order_by_score: bool = True) -> List[Dict]:
    """Retorna leads de uma campanha ordenados por score"""
    order = "ORDER BY score DESC" if order_by_score else ""
    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM leads WHERE campaign_id = %s {order}",
            (campaign_id,)
        )
        return [_row_to_dict(row) for row in cur.fetchall()]


def get_lead(lead_id: str) -> Optional[Dict]:
    """Retorna dados de um lead"""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


# === Lead Status Management (NOVO) ===

def update_lead_status(lead_id: str, status: str, motivo: str = None):
    """Atualiza status do lead (new → queued → contacted → responded/converted/lost)"""
    try:
        with get_cursor() as cur:
            if motivo:
                cur.execute(
                    "UPDATE leads SET status = %s, motivo_descarte = %s, updated_at = NOW() WHERE id = %s",
                    (status, motivo, lead_id)
                )
            else:
                cur.execute(
                    "UPDATE leads SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, lead_id)
                )
    except Exception:
        pass


def update_lead_notes(lead_id: str, notas: str):
    """Adiciona/atualiza notas do lead"""
    try:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE leads SET notas = %s, updated_at = NOW() WHERE id = %s",
                (notas, lead_id)
            )
    except Exception:
        pass


def get_leads_by_status(status: str, campaign_id: str = None) -> List[Dict]:
    """Busca leads por status, opcionalmente filtrado por campanha"""
    with get_cursor() as cur:
        if campaign_id:
            cur.execute(
                "SELECT * FROM leads WHERE status = %s AND campaign_id = %s ORDER BY score DESC",
                (status, campaign_id)
            )
        else:
            cur.execute(
                "SELECT * FROM leads WHERE status = %s ORDER BY score DESC",
                (status,)
            )
        return [_row_to_dict(row) for row in cur.fetchall()]


# === Email Log Functions ===

def log_email_attempt(lead_id: str, campaign_id: str, email_to: str,
                      subject: str, attempt_number: int = 1,
                      body_html: str = '') -> str:
    """Registra tentativa de envio de email"""
    log_id = _generate_id()
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO email_log (id, lead_id, campaign_id, email_to, subject, body_html, status, attempt_number, resend_id, error_message, sent_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, '', '', NULL, NOW())
        """, (log_id, lead_id, campaign_id, email_to, subject, body_html, attempt_number))
    return log_id


def update_email_status(log_id: str, status: str, resend_id: str = None,
                        error_message: str = None):
    """Atualiza status do email enviado e incrementa cache se enviado com sucesso"""
    try:
        with get_cursor() as cur:
            updates = ["status = %s", "sent_at = NOW()"]
            params = [status]

            if resend_id:
                updates.append("resend_id = %s")
                params.append(resend_id)
            if error_message:
                updates.append("error_message = %s")
                params.append(error_message)

            params.append(log_id)
            cur.execute(
                f"UPDATE email_log SET {', '.join(updates)} WHERE id = %s",
                params
            )

            # Incrementa cache da contagem diária se enviado com sucesso
            if status == 'sent':
                increment_daily_count_cache()
    except Exception as e:
        print(f"Erro ao atualizar status do email: {e}")


def get_email_attempts(lead_id: str) -> int:
    """Retorna número de tentativas de email para um lead"""
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as cnt FROM email_log WHERE lead_id = %s",
            (lead_id,)
        )
        row = cur.fetchone()
        return row['cnt'] if row else 0


def get_emails_sent_today() -> int:
    """
    Retorna número de emails enviados hoje.
    Usa cache em memória com TTL de 1 minuto.
    """
    cached_count = get_daily_count_cache()
    if cached_count is not None:
        return cached_count

    with get_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as cnt FROM email_log
            WHERE status = 'sent' AND sent_at::date = CURRENT_DATE
        """)
        row = cur.fetchone()
        count = row['cnt'] if row else 0

    set_daily_count_cache(count)
    return count


def get_email_log_by_campaign(campaign_id: str) -> List[Dict]:
    """Retorna log de emails de uma campanha com nome da clínica"""
    with get_cursor() as cur:
        cur.execute("""
            SELECT el.*, COALESCE(l.nome_clinica, '') as nome_clinica
            FROM email_log el
            LEFT JOIN leads l ON el.lead_id = l.id
            WHERE el.campaign_id = %s
            ORDER BY el.created_at DESC
        """, (campaign_id,))
        return [_row_to_dict(row) for row in cur.fetchall()]


# === Blacklist Functions ===

def add_to_blacklist(email: str, reason: str = "user_request"):
    """Adiciona email à blacklist e invalida cache"""
    if is_blacklisted(email):
        return

    invalidate_blacklist_cache()
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO blacklist (id, email, reason, added_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (email) DO NOTHING
        """, (_generate_id(), email.lower(), reason))


def is_blacklisted(email: str) -> bool:
    """
    Verifica se email está na blacklist.
    Usa cache em memória para evitar chamadas repetidas.
    """
    if not email:
        return False

    email_lower = email.lower()

    # Verifica cache primeiro
    if is_blacklist_cache_valid():
        cached = get_blacklist_cache()
        if cached:
            return email_lower in cached

    # Cache expirado, recarrega
    with get_cursor() as cur:
        cur.execute("SELECT email FROM blacklist")
        rows = cur.fetchall()

    blacklist_emails = {row['email'] for row in rows}
    set_blacklist_cache(blacklist_emails)

    return email_lower in blacklist_emails


def get_blacklist() -> List[Dict]:
    """Retorna todos os emails da blacklist"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM blacklist ORDER BY added_at DESC")
        return [_row_to_dict(row) for row in cur.fetchall()]


def remove_from_blacklist(email: str) -> bool:
    """Remove email da blacklist e invalida cache"""
    if not email:
        return False

    invalidate_blacklist_cache()
    try:
        with get_cursor() as cur:
            cur.execute("DELETE FROM blacklist WHERE LOWER(email) = %s", (email.lower(),))
            return cur.rowcount > 0
    except Exception:
        return False


def add_multiple_to_blacklist(emails: List[str], reason: str = "importacao_manual") -> int:
    """
    Adiciona múltiplos emails à blacklist.
    
    Args:
        emails: Lista de emails para adicionar
        reason: Motivo do bloqueio
        
    Returns:
        Quantidade de emails adicionados (ignora duplicados)
    """
    if not emails:
        return 0

    invalidate_blacklist_cache()
    added = 0
    
    for email in emails:
        email = email.strip().lower()
        if not email or is_blacklisted(email):
            continue
        
        try:
            with get_cursor() as cur:
                cur.execute("""
                    INSERT INTO blacklist (id, email, reason, added_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (email) DO NOTHING
                """, (_generate_id(), email, reason))
                if cur.rowcount > 0:
                    added += 1
        except Exception:
            pass
    
    return added


def get_all_sent_emails(
    limit: int = 50,
    offset: int = 0,
    status: str = None,
    campaign_id: str = None,
    date_from: str = None,
    date_to: str = None
) -> tuple:
    """
    Retorna emails enviados com paginação e filtros.
    
    Args:
        limit: Máximo de registros por página
        offset: Deslocamento para paginação
        status: Filtrar por status ('sent', 'failed', 'pending')
        campaign_id: Filtrar por campanha
        date_from: Data inicial (ISO format)
        date_to: Data final (ISO format)
        
    Returns:
        Tuple (lista_de_emails, total_count)
    """
    conditions = []
    params = []
    
    if status:
        conditions.append("el.status = %s")
        params.append(status)
    
    if campaign_id:
        conditions.append("el.campaign_id = %s")
        params.append(campaign_id)
    
    if date_from:
        conditions.append("el.sent_at >= %s")
        params.append(date_from)
    
    if date_to:
        conditions.append("el.sent_at <= %s")
        params.append(date_to)
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    # Conta total
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) as cnt FROM email_log el
            {where_clause}
        """, params)
        total = cur.fetchone()['cnt']
    
    # Busca página
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT el.*, 
                   COALESCE(l.nome_clinica, '') as nome_clinica,
                   COALESCE(c.name, '') as campaign_name
            FROM email_log el
            LEFT JOIN leads l ON el.lead_id = l.id
            LEFT JOIN campaigns c ON el.campaign_id = c.id
            {where_clause}
            ORDER BY el.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        emails = [_row_to_dict(row) for row in cur.fetchall()]
    
    return emails, total


# === Duplicate/Recent Email Detection ===

def check_email_sent_recently(email: str, days: int = 180) -> Optional[Dict]:
    """Verifica se um email foi contatado com sucesso nos últimos X dias"""
    if not email:
        return None

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    email_lower = email.lower()

    with get_cursor() as cur:
        cur.execute("""
            SELECT el.*, COALESCE(l.nome_clinica, '') as nome_clinica, COALESCE(c.name, '') as campaign_name
            FROM email_log el
            LEFT JOIN leads l ON el.lead_id = l.id
            LEFT JOIN campaigns c ON el.campaign_id = c.id
            WHERE LOWER(el.email_to) = %s AND el.status = 'sent' AND el.sent_at >= %s
            ORDER BY el.sent_at DESC
            LIMIT 1
        """, (email_lower, cutoff))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def get_email_history(email: str) -> List[Dict]:
    """Retorna histórico completo de emails enviados para um endereço"""
    if not email:
        return []

    email_lower = email.lower()
    with get_cursor() as cur:
        cur.execute("""
            SELECT el.*, COALESCE(l.nome_clinica, '') as nome_clinica, COALESCE(c.name, '') as campaign_name
            FROM email_log el
            LEFT JOIN leads l ON el.lead_id = l.id
            LEFT JOIN campaigns c ON el.campaign_id = c.id
            WHERE LOWER(el.email_to) = %s
            ORDER BY el.sent_at DESC
        """, (email_lower,))
        return [_row_to_dict(row) for row in cur.fetchall()]


def check_leads_for_duplicates(leads: List[Dict], days: int = 180) -> tuple:
    """
    Verifica uma lista de leads para encontrar duplicatas recentes.
    OTIMIZADO: Uma query SQL retorna todos os emails contatados recentemente.
    """
    leads_novos = []
    leads_duplicados = []

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # Carrega todos os emails enviados recentemente em uma query
    with get_cursor() as cur:
        cur.execute("""
            SELECT LOWER(email_to) as email, MAX(sent_at) as last_sent_at,
                   MAX(lead_id) as lead_id, MAX(campaign_id) as campaign_id
            FROM email_log
            WHERE status = 'sent' AND sent_at >= %s
            GROUP BY LOWER(email_to)
        """, (cutoff,))
        recent_sends = {}
        for row in cur.fetchall():
            recent_sends[row['email']] = dict(row)

    if not recent_sends:
        for lead in leads:
            lead['is_duplicate'] = False
            leads_novos.append(lead)
        return leads_novos, leads_duplicados

    # Cache para enriquecer dados dos duplicados
    leads_cache = {}
    campaigns_cache = {}

    for lead in leads:
        email = lead.get('contatos', {}).get('email_principal') or lead.get('email_principal')

        if email:
            email_lower = email.lower()
            last_sent = recent_sends.get(email_lower)

            if last_sent:
                lead_id = last_sent.get('lead_id', '')
                campaign_id = last_sent.get('campaign_id', '')

                if lead_id and lead_id not in leads_cache:
                    leads_cache[lead_id] = get_lead(lead_id)
                if campaign_id and campaign_id not in campaigns_cache:
                    campaigns_cache[campaign_id] = get_campaign(campaign_id)

                cached_lead = leads_cache.get(lead_id)
                cached_campaign = campaigns_cache.get(campaign_id)

                sent_info = {
                    'sent_at': last_sent.get('last_sent_at', ''),
                    'nome_clinica': cached_lead.get('nome_clinica', '') if cached_lead else '',
                    'campaign_name': cached_campaign.get('name', '') if cached_campaign else '',
                }
                if isinstance(sent_info['sent_at'], datetime):
                    sent_info['sent_at'] = sent_info['sent_at'].isoformat()

                lead['last_sent_info'] = sent_info
                lead['is_duplicate'] = True
                leads_duplicados.append(lead)
            else:
                lead['is_duplicate'] = False
                leads_novos.append(lead)
        else:
            lead['is_duplicate'] = False
            leads_novos.append(lead)

    return leads_novos, leads_duplicados


# === Settings Functions (NOVO) ===

def get_setting(key: str, default: str = None) -> str:
    """Busca configuração do banco"""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
            row = cur.fetchone()
            return row['value'] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str):
    """Atualiza configuração no banco"""
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()
            """, (key, value, value))
    except Exception:
        pass


def get_all_settings() -> Dict[str, str]:
    """Retorna todas as configurações"""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT key, value FROM settings")
            return {row['key']: row['value'] for row in cur.fetchall()}
    except Exception:
        return {}


# === Email Events Functions (NOVO - para webhooks futuros) ===

def insert_email_event(email_log_id: str, event_type: str, payload: dict = None):
    """Registra evento de email (delivered, opened, bounced, etc.)"""
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO email_events (email_log_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (email_log_id, event_type, json.dumps(payload or {})))
    except Exception:
        pass


def get_email_events(email_log_id: str) -> List[Dict]:
    """Retorna eventos de um email"""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM email_events WHERE email_log_id = %s ORDER BY created_at",
            (email_log_id,)
        )
        return [_row_to_dict(row) for row in cur.fetchall()]


# === Data Loader (para data_viewer.py) ===

def load_table_as_dataframe(table_name: str):
    """Carrega tabela inteira como DataFrame"""
    import pandas as pd
    allowed = {'campaigns', 'leads', 'email_log', 'blacklist'}
    if table_name not in allowed:
        return pd.DataFrame()

    with get_cursor() as cur:
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            # Converte timestamps para string ISO (compatibilidade com o data_viewer)
            for col in df.columns:
                if df[col].dtype == 'datetime64[ns, UTC]' or df[col].dtype == 'object':
                    try:
                        df[col] = df[col].apply(
                            lambda x: x.isoformat() if isinstance(x, datetime) else (str(x) if x is not None else '')
                        )
                    except Exception:
                        pass
            return df
        return pd.DataFrame()


# === Analytics Helpers (NOVO) ===

def get_campaign_summary() -> List[Dict]:
    """Retorna resumo de todas as campanhas com métricas"""
    with get_cursor() as cur:
        cur.execute("""
            SELECT c.*,
                   COUNT(DISTINCT l.id) as actual_leads,
                   COUNT(DISTINCT CASE WHEN el.status = 'sent' THEN el.id END) as actual_sent
            FROM campaigns c
            LEFT JOIN leads l ON l.campaign_id = c.id
            LEFT JOIN email_log el ON el.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """)
        return [_row_to_dict(row) for row in cur.fetchall()]


def get_daily_send_stats(days: int = 30) -> List[Dict]:
    """Retorna contagem de emails por dia"""
    with get_cursor() as cur:
        cur.execute("""
            SELECT sent_at::date as date, COUNT(*) as count
            FROM email_log
            WHERE status = 'sent' AND sent_at >= NOW() - INTERVAL '%s days'
            GROUP BY sent_at::date
            ORDER BY date
        """, (days,))
        return [dict(row) for row in cur.fetchall()]


# Inicializa o banco ao importar o módulo
init_database()
