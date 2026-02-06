"""
Script para adicionar leads manualmente na planilha com dados completos.
Útil para corrigir leads que não foram registrados ou importar leads externos.

Uso:
    # Como módulo
    from scripts.add_leads import add_leads_to_sheet
    leads = [{"nome_clinica": "...", "contatos": {...}, ...}]
    add_leads_to_sheet(leads, campaign_id="minha_campanha")

    # Como script (edite LEADS_DATA abaixo)
    python scripts/add_leads.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Optional
from app.database import get_worksheet, SHEET_COLUMNS, _generate_id, _now_iso
import json


def lead_to_row(lead: Dict, campaign_id: str) -> List:
    """
    Converte um lead do formato JSON para formato de linha da planilha.

    Args:
        lead: Dicionário com dados do lead no formato padrão
        campaign_id: ID da campanha associada

    Returns:
        Lista com valores na ordem das colunas da planilha
    """
    contexto = lead.get('contexto_abordagem', {})
    contatos = lead.get('contatos', {})
    decisor = lead.get('decisor', {})

    return [
        _generate_id(),                              # id
        campaign_id,                                 # campaign_id
        lead.get('nome_clinica', ''),               # nome_clinica
        lead.get('endereco', ''),                   # endereco
        lead.get('cidade_uf', ''),                  # cidade_uf
        lead.get('cnpj', ''),                       # cnpj
        lead.get('site', ''),                       # site
        decisor.get('nome', ''),                    # decisor_nome
        decisor.get('cargo', ''),                   # decisor_cargo
        decisor.get('linkedin', ''),                # decisor_linkedin
        contatos.get('email_principal', ''),        # email_principal
        contatos.get('email_tipo', ''),             # email_tipo
        contatos.get('telefone', ''),               # telefone
        contatos.get('whatsapp', ''),               # whatsapp
        contatos.get('instagram', ''),              # instagram
        lead.get('fonte', ''),                      # fonte
        lead.get('confianca', ''),                  # confianca
        lead.get('score', 0),                       # score
        contexto.get('resumo_clinica', ''),         # resumo_clinica
        contexto.get('perfil_decisor', ''),         # perfil_decisor
        contexto.get('gancho_personalizacao', ''),  # gancho_personalizacao
        contexto.get('dor_provavel', ''),           # dor_provavel
        contexto.get('tom_sugerido', ''),           # tom_sugerido
        json.dumps(lead, ensure_ascii=False),       # raw_data
        _now_iso()                                  # created_at
    ]


def add_leads_to_sheet(
    leads: List[Dict],
    campaign_id: str = "manual_import",
    skip_existing: bool = True,
    verbose: bool = True
) -> Dict:
    """
    Adiciona uma lista de leads na planilha.

    Args:
        leads: Lista de dicionários com dados dos leads
        campaign_id: ID da campanha para associar os leads
        skip_existing: Se True, pula leads cujo email já existe
        verbose: Se True, imprime progresso

    Returns:
        Dicionário com estatísticas: {added, skipped, no_email, errors}
    """
    if verbose:
        print(f"🔄 Adicionando {len(leads)} leads...")

    ws = get_worksheet('leads', fresh=True)

    # Verifica leads já existentes (por email)
    existing_emails = set()
    if skip_existing:
        existing_rows = ws.get_all_values()
        if len(existing_rows) > 1:
            email_col = SHEET_COLUMNS['leads'].index('email_principal')
            for row in existing_rows[1:]:
                if len(row) > email_col and row[email_col]:
                    existing_emails.add(row[email_col].lower())

    if verbose:
        print(f"📋 Leads já registrados: {len(existing_emails)}")

    stats = {"added": 0, "skipped": 0, "no_email": 0, "errors": 0}

    for lead in leads:
        email = lead.get('contatos', {}).get('email_principal', '')
        nome = lead.get('nome_clinica', 'Desconhecido')

        if not email:
            if verbose:
                print(f"⚠️  Sem email: {nome}")
            stats["no_email"] += 1
            continue

        if skip_existing and email.lower() in existing_emails:
            if verbose:
                print(f"⏭️  Já existe: {nome} ({email})")
            stats["skipped"] += 1
            continue

        try:
            row = lead_to_row(lead, campaign_id)

            # Usa insert_row em posição específica para evitar race condition
            all_values = ws.get_all_values()
            next_row = len(all_values) + 1
            ws.insert_row(row, next_row)

            if verbose:
                print(f"✅ Adicionado: {nome} ({email})")
            stats["added"] += 1

            # Atualiza set de emails existentes para evitar duplicatas no mesmo lote
            existing_emails.add(email.lower())

        except Exception as e:
            if verbose:
                print(f"❌ Erro em {nome}: {e}")
            stats["errors"] += 1

    if verbose:
        print(f"\n📊 Resumo:")
        print(f"   ✅ Adicionados: {stats['added']}")
        print(f"   ⏭️  Já existiam: {stats['skipped']}")
        print(f"   ⚠️  Sem email: {stats['no_email']}")
        if stats["errors"]:
            print(f"   ❌ Erros: {stats['errors']}")

    return stats


def add_leads_from_json(json_data: str, campaign_id: str = "manual_import") -> Dict:
    """
    Adiciona leads a partir de uma string JSON.

    Args:
        json_data: String JSON com formato {"leads": [...]} ou lista direta
        campaign_id: ID da campanha

    Returns:
        Estatísticas da operação
    """
    data = json.loads(json_data)

    if isinstance(data, list):
        leads = data
    elif isinstance(data, dict):
        leads = data.get('leads', [])
    else:
        raise ValueError("JSON deve ser uma lista ou objeto com chave 'leads'")

    return add_leads_to_sheet(leads, campaign_id)


# =============================================================================
# EXEMPLO DE USO - Edite LEADS_DATA para adicionar leads manualmente
# =============================================================================

LEADS_DATA = [
    # Exemplo de formato de lead:
    # {
    #     "nome_clinica": "Nome da Clínica",
    #     "endereco": "Rua X, 123 - Bairro",
    #     "cidade_uf": "Cidade - UF",
    #     "cnpj": "00.000.000/0001-00",
    #     "site": "https://...",
    #     "decisor": {
    #         "nome": "Nome do Decisor",
    #         "cargo": "Cargo",
    #         "linkedin": ""
    #     },
    #     "contatos": {
    #         "email_principal": "email@exemplo.com",
    #         "email_tipo": "generico",
    #         "telefone": "(00) 0000-0000",
    #         "whatsapp": "(00) 00000-0000",
    #         "instagram": "@perfil"
    #     },
    #     "contexto_abordagem": {
    #         "resumo_clinica": "...",
    #         "perfil_decisor": "...",
    #         "gancho_personalizacao": "...",
    #         "dor_provavel": "...",
    #         "tom_sugerido": "consultivo|formal|direto|acolhedor"
    #     },
    #     "fonte": "URL de origem",
    #     "confianca": "alta|media|baixa"
    # }
]


if __name__ == "__main__":
    if not LEADS_DATA:
        print("ℹ️  Nenhum lead definido em LEADS_DATA.")
        print("   Edite o arquivo e adicione os leads, ou use como módulo:")
        print("   from scripts.add_leads import add_leads_to_sheet")
    else:
        add_leads_to_sheet(LEADS_DATA, campaign_id="manual_import")
