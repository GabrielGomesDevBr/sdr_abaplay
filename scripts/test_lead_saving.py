#!/usr/bin/env python3
"""
Script de teste para validar que todos os leads são salvos no banco.

Testa:
1. Leads válidos (com email, deve_enviar=True)
2. Leads descartados explicitamente pela IA
3. Leads com deve_enviar=False
4. Leads não processados pela IA
"""
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_worksheet, SHEET_COLUMNS


def test_lead_processing_logic():
    """Testa a lógica de processamento de leads."""

    # Simula entrada de leads
    leads = [
        {"nome_clinica": "Clinica A", "contatos": {"email_principal": "a@test.com"}},
        {"nome_clinica": "Clinica B", "contatos": {"email_principal": "b@test.com"}},
        {"nome_clinica": "Clinica C", "contatos": {"email_principal": ""}},  # Sem email
        {"nome_clinica": "Clinica D", "contatos": {"email_principal": "d@test.com"}},
        {"nome_clinica": "Clinica E", "contatos": {}},  # Sem email
    ]

    # Simula resposta da IA
    llm_result = {
        "leads_processados": [
            {"nome_clinica": "Clinica A", "deve_enviar": True, "score": 85, "insights": "Boa"},
            {"nome_clinica": "Clinica B", "deve_enviar": False, "score": 30, "score_justificativa": "Email genérico"},
        ],
        "leads_descartados": [
            {"nome_clinica": "Clinica C", "motivo": "Sem email válido"},
        ],
        "resumo": {"total_processados": 3, "total_validos": 1, "total_descartados": 2}
    }

    # Aplica a nova lógica
    valid_leads = []
    discarded_leads = []
    processed_names = set()

    # 1. Processa leads_processados
    for proc_lead in llm_result.get('leads_processados', []):
        nome = proc_lead.get('nome_clinica')
        original = next((l for l in leads if l.get('nome_clinica') == nome), None)
        if original:
            processed_names.add(nome)
            original['score'] = proc_lead.get('score', 50)
            original['llm_insights'] = proc_lead.get('insights', '')

            if proc_lead.get('deve_enviar', True):
                valid_leads.append(original)
            else:
                original['discard_reason'] = proc_lead.get('score_justificativa', 'Não enviar')
                discarded_leads.append(original)

    # 2. Processa leads_descartados
    for disc_lead in llm_result.get('leads_descartados', []):
        nome = disc_lead.get('nome_clinica')
        if nome not in processed_names:
            original = next((l for l in leads if l.get('nome_clinica') == nome), None)
            if original:
                processed_names.add(nome)
                original['discard_reason'] = disc_lead.get('motivo', 'Descartado')
                discarded_leads.append(original)

    # 3. Captura leads não processados
    for lead in leads:
        nome = lead.get('nome_clinica')
        if nome and nome not in processed_names:
            lead['discard_reason'] = 'Não processado pela IA'
            discarded_leads.append(lead)
            processed_names.add(nome)

    # Validações
    print("=" * 60)
    print("TESTE DE LÓGICA DE PROCESSAMENTO DE LEADS")
    print("=" * 60)

    print(f"\nEntrada: {len(leads)} leads")
    print(f"Válidos: {len(valid_leads)}")
    print(f"Descartados: {len(discarded_leads)}")
    print(f"Total processado: {len(valid_leads) + len(discarded_leads)}")

    # Verifica se todos foram processados
    total_output = len(valid_leads) + len(discarded_leads)
    assert total_output == len(leads), f"ERRO: {total_output} != {len(leads)}"

    print("\n✅ Todos os leads foram capturados!")

    print("\n--- Leads Válidos ---")
    for lead in valid_leads:
        print(f"  • {lead['nome_clinica']} (score: {lead.get('score', 'N/A')})")

    print("\n--- Leads Descartados ---")
    for lead in discarded_leads:
        print(f"  • {lead['nome_clinica']} - {lead.get('discard_reason', 'N/A')}")

    # Verifica detalhes
    assert len(valid_leads) == 1, "Deveria ter 1 lead válido (Clinica A)"
    assert valid_leads[0]['nome_clinica'] == "Clinica A"

    assert len(discarded_leads) == 4, "Deveria ter 4 leads descartados"
    descarded_names = {l['nome_clinica'] for l in discarded_leads}
    assert descarded_names == {"Clinica B", "Clinica C", "Clinica D", "Clinica E"}

    print("\n✅ Todas as validações passaram!")
    return True


def check_database_leads():
    """Verifica os leads no banco de dados."""
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO DO BANCO DE DADOS")
    print("=" * 60)

    try:
        ws = get_worksheet('leads')
        all_rows = ws.get_all_values()

        if len(all_rows) <= 1:
            print("⚠️  Nenhum lead encontrado no banco")
            return

        headers = all_rows[0]
        leads_count = len(all_rows) - 1

        print(f"\nTotal de leads no banco: {leads_count}")

        # Conta leads com e sem email
        email_col = headers.index('email_principal') if 'email_principal' in headers else -1
        if email_col >= 0:
            with_email = sum(1 for row in all_rows[1:] if len(row) > email_col and row[email_col])
            without_email = leads_count - with_email
            print(f"  • Com email: {with_email}")
            print(f"  • Sem email: {without_email}")

        # Mostra últimos 5 leads
        print("\n--- Últimos 5 leads ---")
        for row in all_rows[-5:]:
            nome = row[2] if len(row) > 2 else 'N/A'
            email = row[10] if len(row) > 10 else 'N/A'
            print(f"  • {nome} | {email or '(sem email)'}")

    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")


def check_email_log():
    """Verifica o email_log no banco de dados."""
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO DO EMAIL LOG")
    print("=" * 60)

    try:
        ws = get_worksheet('email_log')
        all_rows = ws.get_all_values()

        if len(all_rows) <= 1:
            print("⚠️  Nenhum email log encontrado")
            return

        headers = all_rows[0]
        emails_count = len(all_rows) - 1

        print(f"\nTotal de emails no log: {emails_count}")

        # Conta por status
        status_col = headers.index('status') if 'status' in headers else -1
        if status_col >= 0:
            sent = sum(1 for row in all_rows[1:] if len(row) > status_col and row[status_col] == 'sent')
            failed = sum(1 for row in all_rows[1:] if len(row) > status_col and row[status_col] == 'failed')
            pending = emails_count - sent - failed
            print(f"  • Enviados: {sent}")
            print(f"  • Falharam: {failed}")
            print(f"  • Pendentes: {pending}")

    except Exception as e:
        print(f"❌ Erro ao verificar email_log: {e}")


if __name__ == "__main__":
    # Teste da lógica
    test_lead_processing_logic()

    # Verificação do banco
    check_database_leads()
    check_email_log()

    print("\n" + "=" * 60)
    print("TESTES CONCLUÍDOS")
    print("=" * 60)
