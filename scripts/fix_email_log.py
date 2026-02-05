"""
Script para corrigir registros de emails enviados manualmente na planilha
Executar uma única vez para adicionar os 9 emails enviados em 05/02/2026
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from app.database import get_worksheet, SHEET_COLUMNS, _generate_id, _now_iso

# Data base: 05/02/2026 ~08:45 (15 minutos atrás do mais antigo)
BASE_TIME = datetime(2026, 2, 5, 8, 45, 0)

# Emails enviados (ordem da imagem - do mais recente ao mais antigo)
EMAILS_ENVIADOS = [
    {
        "email_to": "neuroenfantneurologiainfantil@gmail.com",
        "subject": "NeuroEnfant: gráficos clínicos integrados",
        "nome_clinica": "NeuroEnfant",
        "minutes_ago": 1
    },
    {
        "email_to": "amajundiai2013@gmail.com", 
        "subject": "AMA Jundiaí: prontuários para renovação de convênios",
        "nome_clinica": "AMA Jundiaí",
        "minutes_ago": 2
    },
    {
        "email_to": "contato@kjuterapias.com.br",
        "subject": "Kju Terapias: diário digital do Daycare",
        "nome_clinica": "Kju Terapias",
        "minutes_ago": 2
    },
    {
        "email_to": "agendamento@auticare.com",
        "subject": "AutiCare (Naples): 1 painel único para decisões",
        "nome_clinica": "AutiCare (Naples Health Service)",
        "minutes_ago": 3
    },
    {
        "email_to": "contato@pediatherapies.com.br",
        "subject": "Pediatherapies: precisão nos registros clínicos",
        "nome_clinica": "Pediatherapies",
        "minutes_ago": 3
    },
    {
        "email_to": "contato@viverejundiai.com.br",
        "subject": "Vivere Jundiaí: dados integrados para sua equipe",
        "nome_clinica": "Clínica Vivere",
        "minutes_ago": 13
    },
    {
        "email_to": "agendas.jundiai@completamenteaba.com.br",
        "subject": "CompletaMente Jundiaí: 3 unidades, 1 sistema",
        "nome_clinica": "CompletaMente ABA (Unidade Jundiaí)",
        "minutes_ago": 13
    },
    {
        "email_to": "secretaria@ateal.org.br",
        "subject": "ATEAL: relatórios padronizados para auditoria",
        "nome_clinica": "ATEAL",
        "minutes_ago": 14
    },
    {
        "email_to": "contato@grupoconduzir.com.br",
        "subject": "Conduzir: supervisão da Academy com gráficos",
        "nome_clinica": "Grupo Conduzir",
        "minutes_ago": 15
    }
]


def main():
    print("🔄 Iniciando correção de registros de email...")
    
    ws = get_worksheet('email_log')
    
    # Verifica emails já existentes para evitar duplicatas
    existing_rows = ws.get_all_values()
    existing_emails = set()
    
    if len(existing_rows) > 1:
        email_col = SHEET_COLUMNS['email_log'].index('email_to')
        for row in existing_rows[1:]:
            if len(row) > email_col:
                existing_emails.add(row[email_col].lower())
    
    print(f"📋 Emails já registrados: {len(existing_emails)}")
    
    # Adiciona emails que faltam
    added = 0
    skipped = 0
    
    for email_data in EMAILS_ENVIADOS:
        email_to = email_data['email_to'].lower()
        
        if email_to in existing_emails:
            print(f"⏭️  Pulando (já existe): {email_to}")
            skipped += 1
            continue
        
        # Calcula timestamp
        sent_time = BASE_TIME + timedelta(minutes=(15 - email_data['minutes_ago']))
        
        # Monta linha seguindo SHEET_COLUMNS['email_log']
        # ['id', 'lead_id', 'campaign_id', 'email_to', 'subject', 'status', 
        #  'attempt_number', 'resend_id', 'error_message', 'sent_at', 'created_at']
        row = [
            _generate_id(),           # id
            'manual',                  # lead_id (não temos)
            'manual',                  # campaign_id 
            email_data['email_to'],   # email_to
            email_data['subject'],    # subject
            'sent',                    # status
            1,                         # attempt_number
            'resend-manual',           # resend_id
            '',                        # error_message
            sent_time.isoformat(),    # sent_at
            sent_time.isoformat()     # created_at
        ]
        
        ws.append_row(row)
        print(f"✅ Adicionado: {email_to} ({email_data['nome_clinica']})")
        added += 1
    
    print(f"\n📊 Resumo:")
    print(f"   ✅ Adicionados: {added}")
    print(f"   ⏭️  Pulados: {skipped}")
    print(f"   📧 Total de envios hoje: {added + len(existing_emails)}")


if __name__ == "__main__":
    main()
