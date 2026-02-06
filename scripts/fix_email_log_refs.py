#!/usr/bin/env python3
"""
Script para corrigir referências de lead_id no email_log.

Problema: Alguns emails têm lead_id='manual' ou IDs que não existem na tabela leads,
mesmo quando o email correspondente existe na tabela leads.

Este script:
1. Carrega todos os leads e cria mapeamento email -> lead_id
2. Encontra emails no log com lead_id inválido
3. Atualiza para o lead_id correto baseado no email
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_worksheet


def fix_email_log_references(dry_run: bool = True):
    """
    Corrige referências de lead_id no email_log.
    """
    print("=" * 60)
    print("CORREÇÃO DE REFERÊNCIAS NO EMAIL_LOG")
    print("=" * 60)
    print(f"Modo: {'DRY RUN' if dry_run else 'EXECUÇÃO REAL'}")
    print()

    # Carrega leads
    ws_leads = get_worksheet('leads', fresh=True)
    leads_data = ws_leads.get_all_values()

    # Cria mapeamento email -> lead_id
    lead_headers = leads_data[0]
    id_col = lead_headers.index('id')
    email_col = lead_headers.index('email_principal')

    email_to_lead_id = {}
    valid_lead_ids = set()

    for row in leads_data[1:]:
        lead_id = row[id_col] if len(row) > id_col else ''
        email = row[email_col].lower() if len(row) > email_col and row[email_col] else ''

        if lead_id and lead_id != 'id':
            valid_lead_ids.add(lead_id)
            if email:
                email_to_lead_id[email] = lead_id

    print(f"Leads válidos: {len(valid_lead_ids)}")
    print(f"Emails mapeados: {len(email_to_lead_id)}")

    # Carrega email_log
    ws_log = get_worksheet('email_log', fresh=True)
    log_data = ws_log.get_all_values()

    log_headers = log_data[0]
    log_id_col = log_headers.index('id')
    log_lead_id_col = log_headers.index('lead_id')
    log_email_col = log_headers.index('email_to')

    # Encontra emails com referência quebrada
    to_fix = []
    for i, row in enumerate(log_data[1:], start=2):
        log_id = row[log_id_col] if len(row) > log_id_col else ''
        current_lead_id = row[log_lead_id_col] if len(row) > log_lead_id_col else ''
        email = row[log_email_col].lower() if len(row) > log_email_col and row[log_email_col] else ''

        # Verifica se lead_id é inválido
        if current_lead_id not in valid_lead_ids:
            # Tenta encontrar lead_id correto pelo email
            correct_lead_id = email_to_lead_id.get(email)
            if correct_lead_id:
                to_fix.append({
                    'row': i,
                    'log_id': log_id,
                    'email': email,
                    'old_lead_id': current_lead_id,
                    'new_lead_id': correct_lead_id
                })

    print(f"Emails a corrigir: {len(to_fix)}")

    if not to_fix:
        print("\n✅ Nenhuma correção necessária.")
        return

    print("\n--- Correções a aplicar ---")
    for item in to_fix:
        print(f"  Row {item['row']}: {item['email'][:40]} | '{item['old_lead_id']}' → '{item['new_lead_id']}'")

    if dry_run:
        print("\n⚠️  DRY RUN: Nenhuma alteração foi feita.")
        return

    # Aplica correções
    print("\n--- Aplicando correções ---")
    for item in to_fix:
        ws_log.update_cell(item['row'], log_lead_id_col + 1, item['new_lead_id'])
    print(f"  ✓ {len(to_fix)} referências corrigidas")

    print("\n✅ Correção concluída!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Corrige referências de lead_id no email_log')
    parser.add_argument('--execute', action='store_true',
                        help='Executa as correções (default: dry-run)')

    args = parser.parse_args()
    fix_email_log_references(dry_run=not args.execute)
