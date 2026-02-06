#!/usr/bin/env python3
"""
Script para corrigir IDs corrompidos na tabela leads.

Problema identificado:
- Todos os leads têm ID="id" em vez de UUIDs únicos
- Isso quebra a relação com email_log

Este script:
1. Gera novos UUIDs para leads com ID corrompido
2. Atualiza email_log para referenciar os IDs corretos (baseado em email)
"""
import sys
from pathlib import Path
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_worksheet, _generate_id


def fix_leads_and_email_log(dry_run: bool = True):
    """
    Corrige IDs na tabela leads e atualiza referências no email_log.
    """
    print("=" * 60)
    print("CORREÇÃO DE IDs CORROMPIDOS")
    print("=" * 60)
    print(f"Modo: {'DRY RUN' if dry_run else 'EXECUÇÃO REAL'}")
    print()

    # Carrega dados
    ws_leads = get_worksheet('leads', fresh=True)
    leads_data = ws_leads.get_all_values()

    ws_log = get_worksheet('email_log', fresh=True)
    log_data = ws_log.get_all_values()

    print(f"Leads no banco: {len(leads_data) - 1}")
    print(f"Emails no log: {len(log_data) - 1}")

    # Identifica leads com ID corrompido
    corrupted_leads = []
    lead_headers = leads_data[0]
    id_col = lead_headers.index('id')
    email_col = lead_headers.index('email_principal')

    for i, row in enumerate(leads_data[1:], start=2):  # Row numbers in sheet (1-indexed + header)
        lead_id = row[id_col] if len(row) > id_col else ''
        email = row[email_col] if len(row) > email_col else ''

        if lead_id == 'id' or not lead_id or len(lead_id) < 4:
            new_id = _generate_id()
            corrupted_leads.append({
                'row': i,
                'old_id': lead_id,
                'new_id': new_id,
                'email': email
            })

    print(f"Leads com ID corrompido: {len(corrupted_leads)}")

    if not corrupted_leads:
        print("\n✅ Nenhum lead com ID corrompido.")
        return

    # Cria mapeamento email -> novo lead_id
    email_to_lead_id = {lead['email']: lead['new_id'] for lead in corrupted_leads if lead['email']}

    # Encontra emails no log que podem ser atualizados
    log_headers = log_data[0]
    log_lead_id_col = log_headers.index('lead_id')
    log_email_col = log_headers.index('email_to')

    emails_to_update = []
    for i, row in enumerate(log_data[1:], start=2):
        log_email = row[log_email_col] if len(row) > log_email_col else ''
        current_lead_id = row[log_lead_id_col] if len(row) > log_lead_id_col else ''

        if log_email in email_to_lead_id:
            new_lead_id = email_to_lead_id[log_email]
            if current_lead_id != new_lead_id:
                emails_to_update.append({
                    'row': i,
                    'email': log_email,
                    'old_lead_id': current_lead_id,
                    'new_lead_id': new_lead_id
                })

    print(f"Emails no log a atualizar: {len(emails_to_update)}")

    # Mostra preview
    print("\n--- Leads a corrigir (primeiros 10) ---")
    for lead in corrupted_leads[:10]:
        print(f"  Row {lead['row']}: {lead['email'][:40]} | {lead['old_id']} → {lead['new_id']}")
    if len(corrupted_leads) > 10:
        print(f"  ... e mais {len(corrupted_leads) - 10}")

    print("\n--- Emails a atualizar (primeiros 10) ---")
    for log in emails_to_update[:10]:
        print(f"  Row {log['row']}: {log['email'][:40]} | {log['old_lead_id']} → {log['new_lead_id']}")
    if len(emails_to_update) > 10:
        print(f"  ... e mais {len(emails_to_update) - 10}")

    if dry_run:
        print("\n⚠️  DRY RUN: Nenhuma alteração foi feita.")
        return

    # Executa correções
    print("\n--- Aplicando correções ---")

    # 1. Corrige IDs nos leads
    print("Corrigindo IDs dos leads...")
    for lead in corrupted_leads:
        ws_leads.update_cell(lead['row'], id_col + 1, lead['new_id'])
    print(f"  ✓ {len(corrupted_leads)} leads corrigidos")

    # 2. Atualiza referências no email_log
    print("Atualizando referências no email_log...")
    for log in emails_to_update:
        ws_log.update_cell(log['row'], log_lead_id_col + 1, log['new_lead_id'])
    print(f"  ✓ {len(emails_to_update)} emails atualizados")

    print("\n✅ Correção concluída!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Corrige IDs corrompidos na tabela leads')
    parser.add_argument('--execute', action='store_true',
                        help='Executa as correções (default: dry-run)')

    args = parser.parse_args()
    fix_leads_and_email_log(dry_run=not args.execute)
