"""
Gerenciamento de banco de dados usando Google Sheets para automação de emails
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import uuid
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    GOOGLE_SHEETS_SPREADSHEET_ID, 
    GOOGLE_SHEETS_CREDENTIALS_PATH,
    BASE_DIR
)

# === Google Sheets Connection ===

# Cache para evitar múltiplas conexões
_client = None
_spreadsheet = None
_worksheets = {}

# Definição das colunas para cada aba
SHEET_COLUMNS = {
    'campaigns': ['id', 'name', 'region', 'created_at', 'status', 'total_leads', 'emails_sent', 'emails_failed'],
    'leads': ['id', 'campaign_id', 'nome_clinica', 'endereco', 'cidade_uf', 'cnpj', 'site',
              'decisor_nome', 'decisor_cargo', 'decisor_linkedin', 'email_principal', 'email_tipo',
              'telefone', 'whatsapp', 'instagram', 'fonte', 'confianca', 'score',
              # Campos do contexto_abordagem (v3.0)
              'resumo_clinica', 'perfil_decisor', 'gancho_personalizacao', 'dor_provavel', 'tom_sugerido',
              'raw_data', 'created_at'],
    'email_log': ['id', 'lead_id', 'campaign_id', 'email_to', 'subject', 'status', 
                  'attempt_number', 'resend_id', 'error_message', 'sent_at', 'created_at'],
    'blacklist': ['id', 'email', 'reason', 'added_at']
}


def _get_credentials():
    """Retorna credenciais do Google"""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Tenta carregar de Streamlit secrets primeiro (para cloud deploy)
    try:
        import streamlit as st
        if "GOOGLE_SHEETS_CREDENTIALS" in st.secrets:
            creds_dict = dict(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
    except Exception:
        pass
    
    # Fallback: carregar do arquivo local
    creds_path = Path(GOOGLE_SHEETS_CREDENTIALS_PATH)
    if not creds_path.is_absolute():
        creds_path = BASE_DIR / GOOGLE_SHEETS_CREDENTIALS_PATH
    
    if creds_path.exists():
        return Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    
    # Fallback: tentar carregar de variável de ambiente
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if creds_json:
        import json
        creds_info = json.loads(creds_json)
        return Credentials.from_service_account_info(creds_info, scopes=scopes)
    
    raise FileNotFoundError(f"Credenciais não encontradas em {creds_path}")


def get_client():
    """Retorna cliente gspread (com cache)"""
    global _client
    if _client is None:
        creds = _get_credentials()
        _client = gspread.authorize(creds)
    return _client


def get_spreadsheet():
    """Retorna a planilha (com cache)"""
    global _spreadsheet
    if _spreadsheet is None:
        client = get_client()
        _spreadsheet = client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
    return _spreadsheet


def get_worksheet(sheet_name: str, fresh: bool = False):
    """
    Retorna uma aba específica (com cache)
    
    Args:
        sheet_name: Nome da aba
        fresh: Se True, força nova busca ignorando cache
    """
    global _worksheets
    
    # Invalida cache se solicitado
    if fresh and sheet_name in _worksheets:
        del _worksheets[sheet_name]
    
    if sheet_name not in _worksheets:
        spreadsheet = get_spreadsheet()
        try:
            _worksheets[sheet_name] = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            # Cria a aba se não existir
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            # Adiciona cabeçalho
            if sheet_name in SHEET_COLUMNS:
                worksheet.update('A1', [SHEET_COLUMNS[sheet_name]])
            _worksheets[sheet_name] = worksheet
    return _worksheets[sheet_name]


def _generate_id() -> str:
    """Gera um ID único"""
    return str(uuid.uuid4())[:8]


def _now_iso() -> str:
    """Retorna timestamp atual em formato ISO"""
    return datetime.now().isoformat()


def _row_to_dict(headers: List[str], row: List) -> Dict:
    """Converte uma linha para dicionário"""
    result = {}
    for i, header in enumerate(headers):
        value = row[i] if i < len(row) else None
        # Converte valores numéricos
        if header in ['score', 'total_leads', 'emails_sent', 'emails_failed', 'attempt_number']:
            try:
                value = int(value) if value else 0
            except (ValueError, TypeError):
                value = 0
        result[header] = value
    return result


def init_database():
    """Inicializa o banco de dados criando as abas necessárias"""
    for sheet_name in SHEET_COLUMNS.keys():
        get_worksheet(sheet_name)


# === Campaign Functions ===

def create_campaign(name: str, region: str = None) -> str:
    """Cria nova campanha e retorna o ID"""
    ws = get_worksheet('campaigns')
    campaign_id = _generate_id()
    
    row = [
        campaign_id,
        name,
        region or '',
        _now_iso(),
        'pending',
        0,  # total_leads
        0,  # emails_sent
        0   # emails_failed
    ]
    ws.append_row(row)
    return campaign_id


def update_campaign_stats(campaign_id: str, total_leads: int = None, 
                          emails_sent: int = None, emails_failed: int = None,
                          status: str = None):
    """Atualiza estatísticas da campanha"""
    ws = get_worksheet('campaigns')
    
    # Encontra a linha da campanha
    try:
        cell = ws.find(campaign_id)
        if not cell:
            return
        
        row_num = cell.row
        headers = SHEET_COLUMNS['campaigns']
        
        updates = []
        if total_leads is not None:
            col = headers.index('total_leads') + 1
            updates.append((row_num, col, total_leads))
        if emails_sent is not None:
            col = headers.index('emails_sent') + 1
            updates.append((row_num, col, emails_sent))
        if emails_failed is not None:
            col = headers.index('emails_failed') + 1
            updates.append((row_num, col, emails_failed))
        if status is not None:
            col = headers.index('status') + 1
            updates.append((row_num, col, status))
        
        for row, col, value in updates:
            ws.update_cell(row, col, value)
    except Exception:
        pass


def get_campaign(campaign_id: str) -> Optional[Dict]:
    """Retorna dados da campanha"""
    ws = get_worksheet('campaigns')
    
    try:
        cell = ws.find(campaign_id)
        if not cell:
            return None
        
        row = ws.row_values(cell.row)
        return _row_to_dict(SHEET_COLUMNS['campaigns'], row)
    except Exception:
        return None


# === Lead Functions ===

def insert_lead(campaign_id: str, lead_data: Dict) -> str:
    """Insere um lead e retorna o ID"""
    ws = get_worksheet('leads')
    lead_id = _generate_id()
    
    # Extrai contexto_abordagem se existir
    contexto = lead_data.get('contexto_abordagem', {})
    
    row = [
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
        lead_data.get('confianca', ''),
        lead_data.get('score', 0),
        # Campos do contexto_abordagem (v3.0)
        contexto.get('resumo_clinica', ''),
        contexto.get('perfil_decisor', ''),
        contexto.get('gancho_personalizacao', ''),
        contexto.get('dor_provavel', ''),
        contexto.get('tom_sugerido', ''),
        json.dumps(lead_data),
        _now_iso()
    ]
    ws.append_row(row)
    return lead_id


def update_lead_score(lead_id: str, score: int):
    """Atualiza o score de um lead"""
    ws = get_worksheet('leads')
    try:
        cell = ws.find(lead_id)
        if cell:
            score_col = SHEET_COLUMNS['leads'].index('score') + 1
            ws.update_cell(cell.row, score_col, score)
    except Exception:
        pass


def get_leads_by_campaign(campaign_id: str, order_by_score: bool = True) -> List[Dict]:
    """Retorna leads de uma campanha ordenados por score"""
    ws = get_worksheet('leads')
    
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:  # Só tem cabeçalho
        return []
    
    headers = SHEET_COLUMNS['leads']
    campaign_id_col = headers.index('campaign_id')
    
    leads = []
    for row in all_rows[1:]:  # Pula cabeçalho
        if len(row) > campaign_id_col and row[campaign_id_col] == campaign_id:
            leads.append(_row_to_dict(headers, row))
    
    if order_by_score:
        leads.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return leads


def get_lead(lead_id: str) -> Optional[Dict]:
    """Retorna dados de um lead"""
    ws = get_worksheet('leads')
    
    try:
        cell = ws.find(lead_id)
        if not cell:
            return None
        
        row = ws.row_values(cell.row)
        return _row_to_dict(SHEET_COLUMNS['leads'], row)
    except Exception:
        return None


# === Email Log Functions ===

def log_email_attempt(lead_id: str, campaign_id: str, email_to: str, 
                      subject: str, attempt_number: int = 1) -> str:
    """Registra tentativa de envio de email"""
    ws = get_worksheet('email_log')
    log_id = _generate_id()
    
    row = [
        log_id,
        lead_id,
        campaign_id,
        email_to,
        subject,
        'pending',
        attempt_number,
        '',  # resend_id
        '',  # error_message
        '',  # sent_at
        _now_iso()
    ]
    ws.append_row(row)
    return log_id


def update_email_status(log_id: str, status: str, resend_id: str = None, 
                        error_message: str = None):
    """Atualiza status do email enviado"""
    ws = get_worksheet('email_log')
    
    try:
        cell = ws.find(log_id)
        if not cell:
            return
        
        row_num = cell.row
        headers = SHEET_COLUMNS['email_log']
        
        # Atualiza status
        ws.update_cell(row_num, headers.index('status') + 1, status)
        
        if resend_id:
            ws.update_cell(row_num, headers.index('resend_id') + 1, resend_id)
        
        if error_message:
            ws.update_cell(row_num, headers.index('error_message') + 1, error_message)
        
        # Atualiza sent_at
        ws.update_cell(row_num, headers.index('sent_at') + 1, _now_iso())
    except Exception:
        pass


def get_email_attempts(lead_id: str) -> int:
    """Retorna número de tentativas de email para um lead"""
    ws = get_worksheet('email_log')
    
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return 0
    
    lead_id_col = SHEET_COLUMNS['email_log'].index('lead_id')
    count = sum(1 for row in all_rows[1:] if len(row) > lead_id_col and row[lead_id_col] == lead_id)
    return count


def get_emails_sent_today() -> int:
    """
    Retorna número de emails enviados hoje.
    SEMPRE busca dados frescos da planilha para garantir contagem precisa.
    """
    # Força refresh do cache para obter dados atualizados
    ws = get_worksheet('email_log', fresh=True)
    
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return 0
    
    headers = SHEET_COLUMNS['email_log']
    status_col = headers.index('status')
    sent_at_col = headers.index('sent_at')
    today = datetime.now().strftime('%Y-%m-%d')
    
    count = 0
    for row in all_rows[1:]:
        # Acesso seguro às colunas (trata linhas com células vazias no final)
        status = row[status_col] if len(row) > status_col else ''
        sent_at = row[sent_at_col] if len(row) > sent_at_col else ''
        
        if status == 'sent' and sent_at.startswith(today):
            count += 1
    return count


def get_email_log_by_campaign(campaign_id: str) -> List[Dict]:
    """Retorna log de emails de uma campanha"""
    ws = get_worksheet('email_log')
    
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    
    headers = SHEET_COLUMNS['email_log']
    campaign_id_col = headers.index('campaign_id')
    
    logs = []
    for row in all_rows[1:]:
        if len(row) > campaign_id_col and row[campaign_id_col] == campaign_id:
            log_dict = _row_to_dict(headers, row)
            # Adiciona nome da clínica do lead
            lead = get_lead(log_dict.get('lead_id', ''))
            log_dict['nome_clinica'] = lead.get('nome_clinica', '') if lead else ''
            logs.append(log_dict)
    
    # Ordena por data de criação (mais recente primeiro)
    logs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return logs


# === Blacklist Functions ===

def add_to_blacklist(email: str, reason: str = "user_request"):
    """Adiciona email à blacklist"""
    if is_blacklisted(email):
        return  # Já existe
    
    ws = get_worksheet('blacklist')
    row = [
        _generate_id(),
        email.lower(),
        reason,
        _now_iso()
    ]
    ws.append_row(row)


def is_blacklisted(email: str) -> bool:
    """Verifica se email está na blacklist"""
    ws = get_worksheet('blacklist')
    
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return False
    
    email_col = SHEET_COLUMNS['blacklist'].index('email')
    email_lower = email.lower()
    
    return any(
        len(row) > email_col and row[email_col] == email_lower 
        for row in all_rows[1:]
    )


def get_blacklist() -> List[Dict]:
    """Retorna todos os emails da blacklist"""
    ws = get_worksheet('blacklist')
    
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    
    headers = SHEET_COLUMNS['blacklist']
    items = [_row_to_dict(headers, row) for row in all_rows[1:]]
    items.sort(key=lambda x: x.get('added_at', ''), reverse=True)
    return items


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
    
    ws = get_worksheet('email_log')
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return None
    
    headers = SHEET_COLUMNS['email_log']
    email_col = headers.index('email_to')
    status_col = headers.index('status')
    sent_at_col = headers.index('sent_at')
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    email_lower = email.lower()
    
    matches = []
    for row in all_rows[1:]:
        if len(row) > max(email_col, status_col, sent_at_col):
            if (row[email_col].lower() == email_lower and 
                row[status_col] == 'sent' and
                row[sent_at_col] >= cutoff_date):
                matches.append(_row_to_dict(headers, row))
    
    if matches:
        # Retorna o mais recente
        matches.sort(key=lambda x: x.get('sent_at', ''), reverse=True)
        result = matches[0]
        
        # Adiciona info do lead e campanha
        lead = get_lead(result.get('lead_id', ''))
        campaign = get_campaign(result.get('campaign_id', ''))
        result['nome_clinica'] = lead.get('nome_clinica', '') if lead else ''
        result['campaign_name'] = campaign.get('name', '') if campaign else ''
        
        return result
    
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
    
    ws = get_worksheet('email_log')
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    
    headers = SHEET_COLUMNS['email_log']
    email_col = headers.index('email_to')
    email_lower = email.lower()
    
    history = []
    for row in all_rows[1:]:
        if len(row) > email_col and row[email_col].lower() == email_lower:
            log_dict = _row_to_dict(headers, row)
            lead = get_lead(log_dict.get('lead_id', ''))
            campaign = get_campaign(log_dict.get('campaign_id', ''))
            log_dict['nome_clinica'] = lead.get('nome_clinica', '') if lead else ''
            log_dict['campaign_name'] = campaign.get('name', '') if campaign else ''
            history.append(log_dict)
    
    history.sort(key=lambda x: x.get('sent_at', ''), reverse=True)
    return history


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
