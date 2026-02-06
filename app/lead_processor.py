"""
Processamento e scoring de leads para automação de emails
"""
import re
import json
from typing import Dict, List, Tuple, Optional

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    SCORE_EMAIL_EXISTS, SCORE_EMAIL_TYPE, SCORE_CONFIDENCE,
    SCORE_DECISOR_IDENTIFIED, SCORE_HAS_WEBSITE
)
from app.database import is_blacklisted


def validate_email_syntax(email: str) -> bool:
    """Valida sintaxe do email"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_email_mx(email: str) -> Tuple[bool, str]:
    """Valida se domínio do email tem MX records"""
    if not DNS_AVAILABLE:
        return True, "DNS validation skipped (dnspython not installed)"
    
    if not email:
        return False, "Email vazio"
    
    try:
        domain = email.split('@')[1]
        mx_records = dns.resolver.resolve(domain, 'MX')
        return True, f"MX válido: {mx_records[0].exchange}"
    except dns.resolver.NXDOMAIN:
        return False, "Domínio não existe"
    except dns.resolver.NoAnswer:
        return False, "Domínio sem MX records"
    except Exception as e:
        return False, f"Erro na validação: {str(e)}"


def calculate_lead_score(lead: Dict) -> int:
    """
    Calcula score de 0-100 para priorização do lead
    
    Critérios:
    - Email existe: +30
    - Tipo de email (nominal, cargo, generico): +0 a +25
    - Confiança (alta, media, baixa): +5 a +25
    - Decisor identificado: +10
    - Site disponível: +10
    """
    score = 0
    
    # Email válido (+30)
    email = lead.get('contatos', {}).get('email_principal')
    if email and validate_email_syntax(email):
        score += SCORE_EMAIL_EXISTS
    else:
        return 0  # Sem email válido = descartado
    
    # Verifica blacklist
    if is_blacklisted(email):
        return -1  # Marcador especial para blacklist
    
    # Tipo de email
    email_type = lead.get('contatos', {}).get('email_tipo', '')
    score += SCORE_EMAIL_TYPE.get(email_type, 0)
    
    # Confiança
    confidence = lead.get('confianca', '')
    score += SCORE_CONFIDENCE.get(confidence, 0)
    
    # Decisor identificado (+10)
    if lead.get('decisor', {}).get('nome'):
        score += SCORE_DECISOR_IDENTIFIED
    
    # Site funcional (+10)
    if lead.get('site'):
        score += SCORE_HAS_WEBSITE
    
    return min(100, score)


def parse_leads_json(json_data: str) -> Tuple[Dict, List[Dict]]:
    """
    Processa JSON de leads e retorna metadados + lista de leads
    
    Returns:
        Tuple[metadata, leads_list]
    """
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido: {str(e)}")
    
    metadata = {
        'regiao_buscada': data.get('regiao_buscada', 'Não especificada'),
        'data_busca': data.get('data_busca', ''),
        'total_retornado': data.get('total_retornado', 0),
        'obs': data.get('obs', '')
    }
    
    leads = data.get('leads', [])
    
    return metadata, leads


def process_leads(leads: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Processa lista de leads, calcula scores e separa válidos de descartados
    
    Returns:
        Tuple[valid_leads, discarded_leads]
    """
    valid_leads = []
    discarded_leads = []
    
    for lead in leads:
        score = calculate_lead_score(lead)
        lead['score'] = score
        
        if score == -1:
            lead['discard_reason'] = 'Email na blacklist'
            discarded_leads.append(lead)
        elif score == 0:
            lead['discard_reason'] = 'Sem email válido'
            discarded_leads.append(lead)
        else:
            # Validação MX adicional
            email = lead.get('contatos', {}).get('email_principal')
            mx_valid, mx_message = validate_email_mx(email)
            lead['mx_valid'] = mx_valid
            lead['mx_message'] = mx_message
            
            if not mx_valid:
                lead['discard_reason'] = f'MX inválido: {mx_message}'
                discarded_leads.append(lead)
            else:
                valid_leads.append(lead)
    
    # Ordena válidos por score (maior primeiro)
    valid_leads.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return valid_leads, discarded_leads


def get_lead_display_info(lead: Dict) -> Dict:
    """Retorna informações formatadas para exibição do lead"""
    email = lead.get('contatos', {}).get('email_principal') or lead.get('email_principal', '')
    decisor = lead.get('decisor', {})
    
    return {
        'nome': lead.get('nome_clinica', 'N/A'),
        'email': email,
        'email_tipo': lead.get('contatos', {}).get('email_tipo') or lead.get('email_tipo', 'N/A'),
        'cidade': lead.get('cidade_uf', 'N/A'),
        'decisor_nome': decisor.get('nome') or lead.get('decisor_nome', 'Não identificado'),
        'decisor_cargo': decisor.get('cargo') or lead.get('decisor_cargo', 'N/A'),
        'score': lead.get('score', 0),
        'confianca': lead.get('confianca', 'N/A'),
        'site': lead.get('site', 'N/A')
    }


def get_template_type(lead: Dict) -> str:
    """Determina qual template usar baseado nos dados do lead"""
    decisor = lead.get('decisor', {})
    if decisor.get('nome'):
        return 'decisor_identificado'
    return 'sem_decisor'


def extract_city_from_lead(lead: Dict) -> str:
    """Extrai apenas a cidade do campo cidade_uf"""
    cidade_uf = lead.get('cidade_uf', '')
    if ' - ' in cidade_uf:
        return cidade_uf.split(' - ')[0].strip()
    return cidade_uf


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DRY - Funções auxiliares para extração de dados de leads
# ═══════════════════════════════════════════════════════════════════════════════

def get_lead_email(lead: Dict) -> str:
    """
    Extrai email do lead independente da estrutura.

    Suporta ambos os formatos:
    - lead['contatos']['email_principal']
    - lead['email_principal']

    Returns:
        Email do lead ou string vazia se não encontrado
    """
    return (
        lead.get('contatos', {}).get('email_principal') or
        lead.get('email_principal') or
        ''
    )


def get_lead_phone(lead: Dict) -> str:
    """
    Extrai telefone do lead independente da estrutura.

    Suporta ambos os formatos:
    - lead['contatos']['telefone']
    - lead['telefone']

    Returns:
        Telefone do lead ou string vazia se não encontrado
    """
    return (
        lead.get('contatos', {}).get('telefone') or
        lead.get('telefone') or
        ''
    )


def get_lead_decisor(lead: Dict) -> Dict:
    """
    Extrai informações do decisor do lead.

    Returns:
        Dict com nome e cargo do decisor
    """
    decisor = lead.get('decisor', {})
    return {
        'nome': decisor.get('nome') or lead.get('decisor_nome', ''),
        'cargo': decisor.get('cargo') or lead.get('decisor_cargo', '')
    }


def get_lead_address(lead: Dict) -> str:
    """
    Extrai endereço formatado do lead.

    Returns:
        Endereço completo ou string vazia
    """
    return (
        lead.get('endereco', {}).get('completo') or
        lead.get('endereco_completo') or
        ''
    )
