"""
Gerenciamento de banco de dados SQLite para automação de emails
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import DATABASE_PATH, DATA_DIR


def get_connection() -> sqlite3.Connection:
    """Retorna conexão com o banco de dados"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Inicializa o banco de dados com as tabelas necessárias"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de campanhas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            region TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            total_leads INTEGER DEFAULT 0,
            emails_sent INTEGER DEFAULT 0,
            emails_failed INTEGER DEFAULT 0
        )
    ''')
    
    # Tabela de leads
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            nome_clinica TEXT NOT NULL,
            endereco TEXT,
            cidade_uf TEXT,
            cnpj TEXT,
            site TEXT,
            decisor_nome TEXT,
            decisor_cargo TEXT,
            decisor_linkedin TEXT,
            email_principal TEXT,
            email_tipo TEXT,
            telefone TEXT,
            whatsapp TEXT,
            instagram TEXT,
            fonte TEXT,
            confianca TEXT,
            score INTEGER DEFAULT 0,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
    ''')
    
    # Tabela de log de emails
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            campaign_id INTEGER,
            email_to TEXT NOT NULL,
            subject TEXT,
            status TEXT DEFAULT 'pending',
            attempt_number INTEGER DEFAULT 1,
            resend_id TEXT,
            error_message TEXT,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id),
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
    ''')
    
    # Tabela de blacklist (opt-out)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            reason TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Índices para performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_leads_campaign ON leads(campaign_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email_principal)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_log_lead ON email_log(lead_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_email ON blacklist(email)')
    
    conn.commit()
    conn.close()


# === Campaign Functions ===

def create_campaign(name: str, region: str = None) -> int:
    """Cria nova campanha e retorna o ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO campaigns (name, region) VALUES (?, ?)',
        (name, region)
    )
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id


def update_campaign_stats(campaign_id: int, total_leads: int = None, 
                          emails_sent: int = None, emails_failed: int = None,
                          status: str = None):
    """Atualiza estatísticas da campanha"""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    values = []
    
    if total_leads is not None:
        updates.append('total_leads = ?')
        values.append(total_leads)
    if emails_sent is not None:
        updates.append('emails_sent = ?')
        values.append(emails_sent)
    if emails_failed is not None:
        updates.append('emails_failed = ?')
        values.append(emails_failed)
    if status is not None:
        updates.append('status = ?')
        values.append(status)
    
    if updates:
        values.append(campaign_id)
        cursor.execute(
            f'UPDATE campaigns SET {", ".join(updates)} WHERE id = ?',
            values
        )
        conn.commit()
    
    conn.close()


def get_campaign(campaign_id: int) -> Optional[Dict]:
    """Retorna dados da campanha"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# === Lead Functions ===

def insert_lead(campaign_id: int, lead_data: Dict) -> int:
    """Insere um lead e retorna o ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO leads (
            campaign_id, nome_clinica, endereco, cidade_uf, cnpj, site,
            decisor_nome, decisor_cargo, decisor_linkedin,
            email_principal, email_tipo, telefone, whatsapp, instagram,
            fonte, confianca, score, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        campaign_id,
        lead_data.get('nome_clinica'),
        lead_data.get('endereco'),
        lead_data.get('cidade_uf'),
        lead_data.get('cnpj'),
        lead_data.get('site'),
        lead_data.get('decisor', {}).get('nome'),
        lead_data.get('decisor', {}).get('cargo'),
        lead_data.get('decisor', {}).get('linkedin'),
        lead_data.get('contatos', {}).get('email_principal'),
        lead_data.get('contatos', {}).get('email_tipo'),
        lead_data.get('contatos', {}).get('telefone'),
        lead_data.get('contatos', {}).get('whatsapp'),
        lead_data.get('contatos', {}).get('instagram'),
        lead_data.get('fonte'),
        lead_data.get('confianca'),
        lead_data.get('score', 0),
        json.dumps(lead_data)
    ))
    
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def update_lead_score(lead_id: int, score: int):
    """Atualiza o score de um lead"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE leads SET score = ? WHERE id = ?', (score, lead_id))
    conn.commit()
    conn.close()


def get_leads_by_campaign(campaign_id: int, order_by_score: bool = True) -> List[Dict]:
    """Retorna leads de uma campanha ordenados por score"""
    conn = get_connection()
    cursor = conn.cursor()
    
    order = 'ORDER BY score DESC' if order_by_score else ''
    cursor.execute(f'SELECT * FROM leads WHERE campaign_id = ? {order}', (campaign_id,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_lead(lead_id: int) -> Optional[Dict]:
    """Retorna dados de um lead"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# === Email Log Functions ===

def log_email_attempt(lead_id: int, campaign_id: int, email_to: str, 
                      subject: str, attempt_number: int = 1) -> int:
    """Registra tentativa de envio de email"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO email_log (lead_id, campaign_id, email_to, subject, attempt_number)
        VALUES (?, ?, ?, ?, ?)
    ''', (lead_id, campaign_id, email_to, subject, attempt_number))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def update_email_status(log_id: int, status: str, resend_id: str = None, 
                        error_message: str = None):
    """Atualiza status do email enviado"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE email_log 
        SET status = ?, resend_id = ?, error_message = ?, sent_at = ?
        WHERE id = ?
    ''', (status, resend_id, error_message, datetime.now(), log_id))
    conn.commit()
    conn.close()


def get_email_attempts(lead_id: int) -> int:
    """Retorna número de tentativas de email para um lead"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COUNT(*) FROM email_log WHERE lead_id = ?', 
        (lead_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_emails_sent_today() -> int:
    """Retorna número de emails enviados hoje"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM email_log 
        WHERE DATE(sent_at) = DATE('now', 'localtime')
        AND status = 'sent'
    ''')
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_email_log_by_campaign(campaign_id: int) -> List[Dict]:
    """Retorna log de emails de uma campanha"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT el.*, l.nome_clinica 
        FROM email_log el
        JOIN leads l ON el.lead_id = l.id
        WHERE el.campaign_id = ?
        ORDER BY el.created_at DESC
    ''', (campaign_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# === Blacklist Functions ===

def add_to_blacklist(email: str, reason: str = "user_request"):
    """Adiciona email à blacklist"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT OR IGNORE INTO blacklist (email, reason) VALUES (?, ?)',
            (email.lower(), reason)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Email já existe na blacklist
    conn.close()


def is_blacklisted(email: str) -> bool:
    """Verifica se email está na blacklist"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COUNT(*) FROM blacklist WHERE email = ?', 
        (email.lower(),)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def get_blacklist() -> List[Dict]:
    """Retorna todos os emails da blacklist"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM blacklist ORDER BY added_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# === Duplicate/Recent Email Detection ===

def check_email_sent_recently(email: str, days: int = 180) -> Optional[Dict]:
    """
    Verifica se um email foi contatado com sucesso nos últimos X dias
    
    Args:
        email: Email para verificar
        days: Número de dias para considerar (default: 180)
        
    Returns:
        Dict com informações do último envio ou None se não encontrado
    """
    if not email:
        return None
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT el.*, l.nome_clinica, c.name as campaign_name
        FROM email_log el
        JOIN leads l ON el.lead_id = l.id
        JOIN campaigns c ON el.campaign_id = c.id
        WHERE el.email_to = ?
        AND el.status = 'sent'
        AND DATE(el.sent_at) >= DATE('now', '-' || ? || ' days')
        ORDER BY el.sent_at DESC
        LIMIT 1
    ''', (email.lower(), days))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_email_history(email: str) -> List[Dict]:
    """
    Retorna histórico completo de emails enviados para um endereço
    
    Args:
        email: Email para consultar
        
    Returns:
        Lista de envios ordenados por data (mais recente primeiro)
    """
    if not email:
        return []
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT el.*, l.nome_clinica, c.name as campaign_name
        FROM email_log el
        JOIN leads l ON el.lead_id = l.id
        JOIN campaigns c ON el.campaign_id = c.id
        WHERE el.email_to = ?
        ORDER BY el.sent_at DESC
    ''', (email.lower(),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def check_leads_for_duplicates(leads: List[Dict], days: int = 180) -> tuple:
    """
    Verifica uma lista de leads para encontrar duplicatas recentes
    
    Args:
        leads: Lista de leads para verificar
        days: Período em dias para considerar duplicata
        
    Returns:
        Tuple (leads_novos, leads_duplicados)
        leads_duplicados inclui 'last_sent_info' com detalhes do último envio
    """
    leads_novos = []
    leads_duplicados = []
    
    for lead in leads:
        email = lead.get('contatos', {}).get('email_principal') or lead.get('email_principal')
        
        if email:
            last_sent = check_email_sent_recently(email, days)
            if last_sent:
                lead['last_sent_info'] = last_sent
                lead['is_duplicate'] = True
                leads_duplicados.append(lead)
            else:
                lead['is_duplicate'] = False
                leads_novos.append(lead)
        else:
            lead['is_duplicate'] = False
            leads_novos.append(lead)
    
    return leads_novos, leads_duplicados


# Inicializa o banco ao importar o módulo
init_database()
