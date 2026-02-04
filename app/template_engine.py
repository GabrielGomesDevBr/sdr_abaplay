"""
Motor de templates de email com personalização
"""
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import TEMPLATES
from app.lead_processor import get_template_type, extract_city_from_lead


def get_template(template_name: str) -> Dict:
    """Retorna template por nome"""
    return TEMPLATES.get(template_name, TEMPLATES['sem_decisor'])


def personalize_template(lead: Dict, template_name: str = None) -> Dict:
    """
    Personaliza template com dados do lead
    
    Args:
        lead: Dados do lead
        template_name: Nome do template (opcional, auto-detecta se não fornecido)
        
    Returns:
        Dict com 'assunto' e 'corpo' personalizados
    """
    if template_name is None:
        template_name = get_template_type(lead)
    
    template = get_template(template_name)
    
    # Extrai dados para personalização
    decisor = lead.get('decisor', {})
    contatos = lead.get('contatos', {})
    
    # Prepara variáveis de substituição
    variables = {
        'nome_clinica': lead.get('nome_clinica', 'sua clínica'),
        'nome_decisor': decisor.get('nome') or lead.get('decisor_nome', ''),
        'cargo_decisor': decisor.get('cargo') or lead.get('decisor_cargo', ''),
        'cidade': extract_city_from_lead(lead),
        'email': contatos.get('email_principal') or lead.get('email_principal', ''),
        'site': lead.get('site', ''),
    }
    
    # Substitui variáveis no assunto e corpo
    assunto = template['assunto']
    corpo = template['corpo']
    
    for key, value in variables.items():
        placeholder = '{' + key + '}'
        assunto = assunto.replace(placeholder, str(value) if value else '')
        corpo = corpo.replace(placeholder, str(value) if value else '')
    
    # Limpa placeholders não substituídos
    import re
    assunto = re.sub(r'\{[^}]+\}', '', assunto)
    corpo = re.sub(r'\{[^}]+\}', '', corpo)
    
    # Remove espaços extras
    assunto = ' '.join(assunto.split())
    
    return {
        'assunto': assunto.strip(),
        'corpo': corpo.strip()
    }


def preview_email(lead: Dict, template_name: str = None) -> str:
    """
    Gera preview do email para exibição
    
    Returns:
        String formatada com preview do email
    """
    personalized = personalize_template(lead, template_name)
    
    preview = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 PREVIEW DO EMAIL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Para: {lead.get('contatos', {}).get('email_principal') or lead.get('email_principal', 'N/A')}
Assunto: {personalized['assunto']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{personalized['corpo']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return preview


def get_available_templates() -> list:
    """Retorna lista de templates disponíveis"""
    return list(TEMPLATES.keys())


def validate_template(template_name: str) -> bool:
    """Verifica se template existe"""
    return template_name in TEMPLATES
