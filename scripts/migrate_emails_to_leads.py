#!/usr/bin/env python3
"""
Script de migração: Emails sem lead correspondente → tabela leads

Este script:
1. Encontra emails no email_log que não têm lead_id correspondente na tabela leads
2. Cria entradas de lead básicas para esses emails
3. Preserva o vínculo campaign_id

Uso:
    python scripts/migrate_emails_to_leads.py --dry-run  # Apenas mostra o que seria feito
    python scripts/migrate_emails_to_leads.py            # Executa a migração
"""
import sys
from pathlib import Path
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_worksheet, SHEET_COLUMNS, _generate_id, _now_iso


def get_all_leads():
    """Retorna todos os leads do banco."""
    ws = get_worksheet('leads')
    all_rows = ws.get_all_values()

    if len(all_rows) <= 1:
        return {}

    headers = all_rows[0]
    leads = {}

    for row in all_rows[1:]:
        lead_id = row[0] if row else None
        if lead_id:
            lead_dict = {headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))}
            leads[lead_id] = lead_dict

    return leads


def get_all_email_logs():
    """Retorna todos os logs de email."""
    ws = get_worksheet('email_log')
    all_rows = ws.get_all_values()

    if len(all_rows) <= 1:
        return []

    headers = all_rows[0]
    logs = []

    for row in all_rows[1:]:
        log_dict = {headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))}
        logs.append(log_dict)

    return logs


def find_orphan_emails(leads: dict, email_logs: list) -> list:
    """
    Encontra emails que não têm lead correspondente.

    Args:
        leads: Dicionário de leads {id: dados}
        email_logs: Lista de logs de email

    Returns:
        Lista de emails órfãos (sem lead no banco)
    """
    orphans = []
    lead_ids = set(leads.keys())

    for log in email_logs:
        lead_id = log.get('lead_id', '')
        if lead_id and lead_id not in lead_ids:
            orphans.append(log)

    return orphans


def extract_clinic_name_from_email(email: str) -> str:
    """Tenta extrair nome da clínica do email."""
    if not email:
        return "Lead migrado"

    # Remove o domínio
    local_part = email.split('@')[0]

    # Padrões comuns
    if local_part in ['contato', 'contato', 'info', 'atendimento', 'agendamento']:
        # Tenta usar o domínio
        domain = email.split('@')[1].split('.')[0] if '@' in email else ''
        return domain.title() if domain else "Lead migrado"

    return local_part.replace('.', ' ').replace('_', ' ').title()


def create_lead_from_email(email_log: dict) -> dict:
    """
    Cria dados de lead a partir do email_log.

    Args:
        email_log: Dados do email

    Returns:
        Dicionário com dados do lead
    """
    email = email_log.get('email_to', '')
    campaign_id = email_log.get('campaign_id', '')
    sent_at = email_log.get('sent_at', '')

    # Tenta extrair nome da clínica do campo nome_clinica se existir, senão do email
    nome = email_log.get('nome_clinica') or extract_clinic_name_from_email(email)

    return {
        'id': _generate_id(),
        'campaign_id': campaign_id,
        'nome_clinica': nome,
        'endereco': '',
        'cidade_uf': '',
        'cnpj': '',
        'site': '',
        'decisor_nome': '',
        'decisor_cargo': '',
        'decisor_linkedin': '',
        'email_principal': email,
        'email_tipo': 'migrado',
        'telefone': '',
        'whatsapp': '',
        'instagram': '',
        'fonte': 'migrado_email_log',
        'confianca': 'baixa',
        'score': 0,
        # Campos contexto_abordagem vazios
        'resumo_clinica': '',
        'perfil_decisor': '',
        'gancho_personalizacao': '',
        'dor_provavel': '',
        'tom_sugerido': '',
        'raw_data': f'{{"migrado_de": "email_log", "email_original": "{email}", "sent_at": "{sent_at}"}}',
        'created_at': _now_iso()
    }


def find_email_log_row(ws_log, log_id: str) -> int:
    """Encontra a linha no email_log pelo ID."""
    all_rows = ws_log.get_all_values()
    for i, row in enumerate(all_rows[1:], start=2):
        if row and row[0] == log_id:
            return i
    return -1


def migrate_orphan_emails(dry_run: bool = True):
    """
    Executa a migração de emails órfãos para leads.

    Args:
        dry_run: Se True, apenas mostra o que seria feito
    """
    print("=" * 60)
    print("MIGRAÇÃO: EMAILS → LEADS")
    print("=" * 60)
    print(f"Modo: {'DRY RUN (simulação)' if dry_run else 'EXECUÇÃO REAL'}")
    print()

    # Carrega dados
    print("Carregando dados...")
    leads = get_all_leads()
    email_logs = get_all_email_logs()

    print(f"  • Leads no banco: {len(leads)}")
    print(f"  • Emails no log: {len(email_logs)}")

    # Encontra órfãos
    orphans = find_orphan_emails(leads, email_logs)
    print(f"  • Emails órfãos (sem lead): {len(orphans)}")

    if not orphans:
        print("\n✅ Nenhum email órfão encontrado. Nada a migrar.")
        return

    print("\n--- Emails a migrar ---")
    for i, orphan in enumerate(orphans, 1):
        email = orphan.get('email_to', 'N/A')
        lead_id = orphan.get('lead_id', 'N/A')
        campaign = orphan.get('campaign_id', 'N/A')
        print(f"  {i}. {email} (lead_id: {lead_id}, campaign: {campaign})")

    if dry_run:
        print("\n⚠️  DRY RUN: Nenhuma alteração foi feita.")
        print("    Execute sem --dry-run para aplicar as alterações.")
        return

    # Executa migração
    print("\n--- Executando migração ---")
    ws_leads = get_worksheet('leads', fresh=True)
    ws_log = get_worksheet('email_log', fresh=True)
    migrated = 0

    for orphan in orphans:
        lead_data = create_lead_from_email(orphan)
        old_lead_id = orphan.get('lead_id', '')
        new_lead_id = lead_data['id']
        log_id = orphan.get('id', '')

        # Cria linha para inserir
        row = [
            lead_data['id'],
            lead_data['campaign_id'],
            lead_data['nome_clinica'],
            lead_data['endereco'],
            lead_data['cidade_uf'],
            lead_data['cnpj'],
            lead_data['site'],
            lead_data['decisor_nome'],
            lead_data['decisor_cargo'],
            lead_data['decisor_linkedin'],
            lead_data['email_principal'],
            lead_data['email_tipo'],
            lead_data['telefone'],
            lead_data['whatsapp'],
            lead_data['instagram'],
            lead_data['fonte'],
            lead_data['confianca'],
            lead_data['score'],
            lead_data['resumo_clinica'],
            lead_data['perfil_decisor'],
            lead_data['gancho_personalizacao'],
            lead_data['dor_provavel'],
            lead_data['tom_sugerido'],
            lead_data['raw_data'],
            lead_data['created_at']
        ]

        # 1. Insere o lead (usando insert_row para garantir inserção)
        all_values = ws_leads.get_all_values()
        next_row = len(all_values) + 1
        ws_leads.insert_row(row, next_row)

        # 2. Atualiza o email_log para referenciar o novo lead_id
        log_row = find_email_log_row(ws_log, log_id)
        if log_row > 0:
            ws_log.update_cell(log_row, 2, new_lead_id)  # Coluna 2 = lead_id

        migrated += 1
        print(f"  ✓ Migrado: {lead_data['email_principal']} → lead {new_lead_id} (log row {log_row})")

    print(f"\n✅ Migração concluída: {migrated} leads criados")


def main():
    """Função principal."""
    import argparse

    parser = argparse.ArgumentParser(description='Migra emails órfãos para tabela leads')
    parser.add_argument('--execute', action='store_true',
                        help='Executa a migração (default: dry-run)')

    args = parser.parse_args()
    migrate_orphan_emails(dry_run=not args.execute)


if __name__ == "__main__":
    main()
