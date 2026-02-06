"""
Script de migração: Google Sheets → Neon PostgreSQL

Lê todos os dados das 4 abas da planilha e insere no banco SQL,
respeitando a ordem de foreign keys e preenchendo campos novos.

Uso:
    python scripts/migrate_to_sql.py              # Modo dry-run (não insere)
    python scripts/migrate_to_sql.py --execute    # Executa migração
"""
import sys
import os
import json
import uuid
from pathlib import Path
from datetime import datetime

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials
import psycopg2
from psycopg2.extras import execute_values

# === Config ===
SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
CREDENTIALS_PATH = Path(__file__).parent.parent / os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'credentials.json')
DATABASE_URL = os.getenv('DATABASE_URL')

SHEET_COLUMNS = {
    'campaigns': ['id', 'name', 'region', 'created_at', 'status', 'total_leads', 'emails_sent', 'emails_failed'],
    'leads': ['id', 'campaign_id', 'nome_clinica', 'endereco', 'cidade_uf', 'cnpj', 'site',
              'decisor_nome', 'decisor_cargo', 'decisor_linkedin', 'email_principal', 'email_tipo',
              'telefone', 'whatsapp', 'instagram', 'fonte', 'confianca', 'score',
              'resumo_clinica', 'perfil_decisor', 'gancho_personalizacao', 'dor_provavel', 'tom_sugerido',
              'raw_data', 'created_at'],
    'email_log': ['id', 'lead_id', 'campaign_id', 'email_to', 'subject', 'status',
                  'attempt_number', 'resend_id', 'error_message', 'sent_at', 'created_at'],
    'blacklist': ['id', 'email', 'reason', 'added_at']
}


def connect_sheets():
    """Conecta ao Google Sheets"""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def connect_sql():
    """Conecta ao Neon PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)


def read_sheet(spreadsheet, sheet_name):
    """Lê todos os dados de uma aba como lista de dicts"""
    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        print(f"  [WARN] Aba '{sheet_name}' não encontrada, pulando...")
        return []

    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return []

    headers = SHEET_COLUMNS.get(sheet_name, all_values[0])
    rows = []
    for row in all_values[1:]:
        d = {}
        for i, h in enumerate(headers):
            d[h] = row[i] if i < len(row) else ''
        rows.append(d)
    return rows


def safe_int(val, default=0):
    """Converte para int com fallback"""
    try:
        return int(val) if val else default
    except (ValueError, TypeError):
        return default


def safe_timestamp(val):
    """Converte ISO timestamp ou retorna None"""
    if not val or val.strip() == '':
        return None
    return val


def generate_id():
    """Gera ID curto"""
    return str(uuid.uuid4())[:8]


def migrate_campaigns(cur, rows, dry_run=True):
    """Migra campanhas"""
    print(f"\n{'='*50}")
    print(f"CAMPAIGNS: {len(rows)} registros")
    print(f"{'='*50}")

    valid = []
    seen_ids = set()
    for row in rows:
        rid = row.get('id', '').strip()
        if not rid or rid == 'id' or rid in seen_ids:
            old_id = rid
            rid = generate_id()
            print(f"  [FIX] ID '{old_id}' → '{rid}' (campanha: {row.get('name', 'N/A')})")
        seen_ids.add(rid)

        valid.append((
            rid,
            row.get('name', ''),
            row.get('region', ''),
            '',  # description (novo)
            safe_timestamp(row.get('created_at')),
            safe_timestamp(row.get('created_at')),  # updated_at = created_at
            row.get('status', 'pending') or 'pending',
            safe_int(row.get('total_leads')),
            safe_int(row.get('emails_sent')),
            safe_int(row.get('emails_failed')),
        ))

    if not dry_run and valid:
        execute_values(cur, """
            INSERT INTO campaigns (id, name, region, description, created_at, updated_at, status, total_leads, emails_sent, emails_failed)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """, valid)

    print(f"  → {len(valid)} campanhas para inserir")
    return {v[0]: v[1] for v in valid}  # id → name


def migrate_leads(cur, rows, valid_campaign_ids, dry_run=True):
    """Migra leads"""
    print(f"\n{'='*50}")
    print(f"LEADS: {len(rows)} registros")
    print(f"{'='*50}")

    valid = []
    orphan_count = 0
    seen_ids = set()
    id_map = {}  # old_id → new_id (para corrigir referências no email_log)

    for row in rows:
        rid = row.get('id', '').strip()
        campaign_id = row.get('campaign_id', '').strip()

        # Fix ID
        original_id = rid
        if not rid or rid == 'id' or rid in seen_ids:
            rid = generate_id()
            print(f"  [FIX] ID '{original_id}' → '{rid}' (lead: {row.get('nome_clinica', 'N/A')})")
        if original_id and original_id != rid:
            id_map[original_id] = rid
        seen_ids.add(rid)

        # Verifica FK campaign_id - cria campanha placeholder se necessário
        if campaign_id and campaign_id not in valid_campaign_ids:
            orphan_count += 1
            placeholder_id = campaign_id if len(campaign_id) <= 8 else str(uuid.uuid5(uuid.NAMESPACE_DNS, campaign_id))[:8]
            print(f"  [FIX] Criando campanha placeholder '{placeholder_id}' para lead '{row.get('nome_clinica')}'")
            if not dry_run:
                cur.execute("""
                    INSERT INTO campaigns (id, name, region, description, created_at, updated_at, status, total_leads, emails_sent, emails_failed)
                    VALUES (%s, %s, %s, %s, NOW(), NOW(), 'completed', 0, 0, 0)
                    ON CONFLICT (id) DO NOTHING
                """, (placeholder_id, f'[Migrada] {campaign_id}', '', f'Campanha criada automaticamente durante migracao para campaign_id={campaign_id}'))
            valid_campaign_ids.add(placeholder_id)
            campaign_id = placeholder_id
        elif not campaign_id:
            orphan_count += 1
            print(f"  [WARN] Lead '{row.get('nome_clinica')}' sem campaign_id, pulando")
            continue

        # Score com validação
        score = safe_int(row.get('score'))
        score = max(0, min(100, score))

        # Confiança com validação
        confianca = row.get('confianca', '').strip()
        if confianca not in ('', 'alta', 'media', 'baixa'):
            confianca = ''

        # raw_data como JSONB
        raw = row.get('raw_data', '')
        try:
            raw_json = json.loads(raw) if raw else None
        except (json.JSONDecodeError, TypeError):
            raw_json = None

        valid.append((
            rid,
            campaign_id,
            'new',  # status (novo campo)
            row.get('nome_clinica', ''),
            row.get('endereco', ''),
            row.get('cidade_uf', ''),
            row.get('cnpj', ''),
            row.get('site', ''),
            row.get('decisor_nome', ''),
            row.get('decisor_cargo', ''),
            row.get('decisor_linkedin', ''),
            row.get('email_principal', ''),
            row.get('email_tipo', ''),
            row.get('telefone', ''),
            row.get('whatsapp', ''),
            row.get('instagram', ''),
            row.get('fonte', ''),
            confianca,
            score,
            row.get('resumo_clinica', ''),
            row.get('perfil_decisor', ''),
            row.get('gancho_personalizacao', ''),
            row.get('dor_provavel', ''),
            row.get('tom_sugerido', ''),
            '',  # notas (novo)
            '',  # motivo_descarte (novo)
            json.dumps(raw_json) if raw_json else None,
            safe_timestamp(row.get('created_at')),
            safe_timestamp(row.get('created_at')),  # updated_at = created_at
        ))

    if not dry_run and valid:
        execute_values(cur, """
            INSERT INTO leads (
                id, campaign_id, status, nome_clinica, endereco, cidade_uf, cnpj, site,
                decisor_nome, decisor_cargo, decisor_linkedin, email_principal, email_tipo,
                telefone, whatsapp, instagram, fonte, confianca, score,
                resumo_clinica, perfil_decisor, gancho_personalizacao, dor_provavel, tom_sugerido,
                notas, motivo_descarte, raw_data, created_at, updated_at
            ) VALUES %s
            ON CONFLICT (id) DO NOTHING
        """, valid)

    print(f"  → {len(valid)} leads para inserir, {orphan_count} órfãos ignorados")
    return {v[0] for v in valid}, id_map  # set de IDs válidos


def migrate_email_log(cur, rows, valid_lead_ids, valid_campaign_ids, lead_id_map, dry_run=True):
    """Migra email_log"""
    print(f"\n{'='*50}")
    print(f"EMAIL_LOG: {len(rows)} registros")
    print(f"{'='*50}")

    valid = []
    orphan_leads = 0
    orphan_campaigns = 0
    seen_ids = set()

    for row in rows:
        rid = row.get('id', '').strip()
        lead_id = row.get('lead_id', '').strip()
        campaign_id = row.get('campaign_id', '').strip()

        # Fix ID
        if not rid or rid == 'id' or rid in seen_ids:
            old = rid
            rid = generate_id()
            print(f"  [FIX] ID '{old}' → '{rid}'")
        seen_ids.add(rid)

        # Corrige lead_id usando mapa
        if lead_id in lead_id_map:
            lead_id = lead_id_map[lead_id]

        # Valida FKs (permite NULL para órfãos)
        if lead_id and lead_id not in valid_lead_ids:
            if lead_id != 'manual':
                orphan_leads += 1
            lead_id = None  # SET NULL para órfãos

        if campaign_id and campaign_id not in valid_campaign_ids:
            # Cria campanha placeholder
            placeholder_id = campaign_id if len(campaign_id) <= 8 else str(uuid.uuid5(uuid.NAMESPACE_DNS, campaign_id))[:8]
            if not dry_run:
                cur.execute("""
                    INSERT INTO campaigns (id, name, region, description, created_at, updated_at, status, total_leads, emails_sent, emails_failed)
                    VALUES (%s, %s, '', %s, NOW(), NOW(), 'completed', 0, 0, 0)
                    ON CONFLICT (id) DO NOTHING
                """, (placeholder_id, f'[Migrada] {campaign_id}', f'Campanha criada para email_log com campaign_id={campaign_id}'))
            valid_campaign_ids.add(placeholder_id)
            campaign_id = placeholder_id
            orphan_campaigns += 1

        # Status com validação
        status = row.get('status', 'pending').strip()
        if status not in ('pending', 'sent', 'failed', 'bounced', 'rejected'):
            status = 'pending'

        valid.append((
            rid,
            lead_id or None,
            campaign_id or None,
            row.get('email_to', ''),
            row.get('subject', ''),
            '',  # body_html (novo, não existia antes)
            status,
            safe_int(row.get('attempt_number'), 1),
            row.get('resend_id', ''),
            row.get('error_message', ''),
            safe_timestamp(row.get('sent_at')),
            safe_timestamp(row.get('created_at')),
        ))

    if not dry_run and valid:
        execute_values(cur, """
            INSERT INTO email_log (
                id, lead_id, campaign_id, email_to, subject, body_html, status,
                attempt_number, resend_id, error_message, sent_at, created_at
            ) VALUES %s
            ON CONFLICT (id) DO NOTHING
        """, valid)

    print(f"  → {len(valid)} emails para inserir")
    if orphan_leads > 0:
        print(f"  → {orphan_leads} com lead_id órfão (SET NULL)")
    if orphan_campaigns > 0:
        print(f"  → {orphan_campaigns} com campaign_id órfão (SET NULL)")


def migrate_blacklist(cur, rows, dry_run=True):
    """Migra blacklist"""
    print(f"\n{'='*50}")
    print(f"BLACKLIST: {len(rows)} registros")
    print(f"{'='*50}")

    valid = []
    seen_emails = set()
    seen_ids = set()

    for row in rows:
        rid = row.get('id', '').strip()
        email = row.get('email', '').strip().lower()

        if not email:
            continue

        if email in seen_emails:
            print(f"  [SKIP] Email duplicado: {email}")
            continue
        seen_emails.add(email)

        if not rid or rid == 'id' or rid in seen_ids:
            rid = generate_id()
        seen_ids.add(rid)

        # Valida reason
        reason = row.get('reason', 'user_request').strip()
        if reason not in ('user_request', 'hard_bounce', 'spam_complaint', 'manual', 'invalid_email'):
            reason = 'user_request'

        valid.append((
            rid,
            email,
            reason,
            None,  # source_campaign_id (não existia antes)
            safe_timestamp(row.get('added_at')),
        ))

    if not dry_run and valid:
        execute_values(cur, """
            INSERT INTO blacklist (id, email, reason, source_campaign_id, added_at)
            VALUES %s
            ON CONFLICT (email) DO NOTHING
        """, valid)

    print(f"  → {len(valid)} emails para inserir")


def update_lead_statuses(cur, dry_run=True):
    """Atualiza leads.status baseado no email_log existente"""
    print(f"\n{'='*50}")
    print("ATUALIZANDO STATUS DOS LEADS")
    print(f"{'='*50}")

    if not dry_run:
        cur.execute("""
            UPDATE leads SET status = 'contacted', updated_at = NOW()
            WHERE id IN (
                SELECT DISTINCT lead_id FROM email_log
                WHERE status = 'sent' AND lead_id IS NOT NULL
            )
        """)
        count = cur.rowcount
        print(f"  → {count} leads atualizados para 'contacted'")
    else:
        cur.execute("""
            SELECT COUNT(DISTINCT lead_id) FROM email_log
            WHERE status = 'sent' AND lead_id IS NOT NULL
        """)
        count = cur.fetchone()[0]
        print(f"  → {count} leads seriam atualizados para 'contacted'")


def main():
    dry_run = '--execute' not in sys.argv

    if dry_run:
        print("=" * 60)
        print("  MODO DRY-RUN (use --execute para migrar de verdade)")
        print("=" * 60)
    else:
        print("=" * 60)
        print("  EXECUTANDO MIGRAÇÃO REAL")
        print("=" * 60)

    # 1. Conectar
    print("\n[1/7] Conectando ao Google Sheets...")
    spreadsheet = connect_sheets()
    print("  OK")

    print("[2/7] Conectando ao Neon PostgreSQL...")
    conn = connect_sql()
    conn.autocommit = False
    cur = conn.cursor()
    print("  OK")

    try:
        # 2. Ler dados do Sheets
        print("\n[3/7] Lendo dados do Google Sheets...")
        campaigns_data = read_sheet(spreadsheet, 'campaigns')
        leads_data = read_sheet(spreadsheet, 'leads')
        email_log_data = read_sheet(spreadsheet, 'email_log')
        blacklist_data = read_sheet(spreadsheet, 'blacklist')

        print(f"  Campaigns: {len(campaigns_data)}")
        print(f"  Leads: {len(leads_data)}")
        print(f"  Email Log: {len(email_log_data)}")
        print(f"  Blacklist: {len(blacklist_data)}")

        # 3. Migrar na ordem correta
        print("\n[4/7] Migrando campanhas...")
        campaign_ids = migrate_campaigns(cur, campaigns_data, dry_run)

        print("\n[5/7] Migrando leads...")
        lead_ids, lead_id_map = migrate_leads(cur, leads_data, set(campaign_ids.keys()), dry_run)

        print("\n[6/7] Migrando email_log...")
        migrate_email_log(cur, email_log_data, lead_ids, set(campaign_ids.keys()), lead_id_map, dry_run)

        print("\n[7/7] Migrando blacklist...")
        migrate_blacklist(cur, blacklist_data, dry_run)

        # 4. Atualizar status dos leads
        update_lead_statuses(cur, dry_run)

        if not dry_run:
            conn.commit()
            print("\n" + "=" * 60)
            print("  MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 60)

            # Validação
            print("\n[VALIDAÇÃO] Contagens no SQL:")
            for table in ['campaigns', 'leads', 'email_log', 'blacklist', 'settings']:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  {table}: {count}")
        else:
            conn.rollback()
            print("\n" + "=" * 60)
            print("  DRY-RUN CONCLUÍDO (nenhum dado foi alterado)")
            print("  Use: python scripts/migrate_to_sql.py --execute")
            print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
