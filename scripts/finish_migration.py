"""
Finaliza a migração Neon → Render via psycopg2 direto.
Importa as tabelas restantes: email_log (575 faltando), blacklist, settings.
Usa queries parametrizadas + ON CONFLICT DO NOTHING (seguro para re-execução).
"""
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import sys

NEON_URL = "postgresql://neondb_owner:NEON_PASSWORD_REDACTED@ep-dawn-firefly-a83lnrqc-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
RENDER_URL = "postgresql://abaplay_postgres_db_user:RENDER_PASSWORD_REDACTED@dpg-d07n3madbo4c73ehoiqg-a.oregon-postgres.render.com/abaplay_postgres_db"

def migrate_email_log(neon_cur, render_cur):
    neon_cur.execute("SELECT id, lead_id, campaign_id, email_to, subject, body_html, status, attempt_number, resend_id, error_message, sent_at, created_at FROM email_log")
    rows = neon_cur.fetchall()
    data = [(r['id'], r['lead_id'], r['campaign_id'], r['email_to'], r['subject'], r['body_html'],
             r['status'], r['attempt_number'], r['resend_id'], r['error_message'], r['sent_at'], r['created_at'])
            for r in rows]
    execute_values(render_cur, """
        INSERT INTO sdr.email_log (id, lead_id, campaign_id, email_to, subject, body_html, status, attempt_number, resend_id, error_message, sent_at, created_at)
        VALUES %s ON CONFLICT (id) DO NOTHING
    """, data, page_size=50)
    return len(data)

def migrate_blacklist(neon_cur, render_cur):
    neon_cur.execute("SELECT id, email, reason, source_campaign_id, added_at FROM blacklist")
    rows = neon_cur.fetchall()
    data = [(r['id'], r['email'], r['reason'], r['source_campaign_id'], r['added_at']) for r in rows]
    execute_values(render_cur, """
        INSERT INTO sdr.blacklist (id, email, reason, source_campaign_id, added_at)
        VALUES %s ON CONFLICT (id) DO NOTHING
    """, data)
    return len(data)

def migrate_settings(neon_cur, render_cur):
    neon_cur.execute("SELECT key, value, description, updated_at FROM settings")
    rows = neon_cur.fetchall()
    data = [(r['key'], r['value'], r['description'], r['updated_at']) for r in rows]
    execute_values(render_cur, """
        INSERT INTO sdr.settings (key, value, description, updated_at)
        VALUES %s ON CONFLICT (key) DO NOTHING
    """, data)
    return len(data)

def check_counts(render_cur):
    for table in ['email_log', 'blacklist', 'settings']:
        render_cur.execute(f"SELECT COUNT(*) FROM sdr.{table}")
        print(f"  sdr.{table}: {render_cur.fetchone()[0]} rows")

def main():
    print("Conectando ao Neon...", flush=True)
    neon = psycopg2.connect(NEON_URL, connect_timeout=15)
    neon_cur = neon.cursor(cursor_factory=RealDictCursor)

    print("Conectando ao Render...", flush=True)
    render = psycopg2.connect(RENDER_URL, connect_timeout=15)
    render.autocommit = False
    render_cur = render.cursor()

    try:
        print("\nMigrando email_log...", flush=True)
        n = migrate_email_log(neon_cur, render_cur)
        print(f"  {n} rows processadas (ON CONFLICT DO NOTHING para duplicatas)")

        print("Migrando blacklist...", flush=True)
        n = migrate_blacklist(neon_cur, render_cur)
        print(f"  {n} rows processadas")

        print("Migrando settings...", flush=True)
        n = migrate_settings(neon_cur, render_cur)
        print(f"  {n} rows processadas")

        render.commit()
        print("\nCOMMIT OK")

        print("\nContagens finais no Render (sdr):")
        render_cur2 = render.cursor()
        check_counts(render_cur2)

    except Exception as e:
        render.rollback()
        print(f"\nERRO — rollback executado: {e}", file=sys.stderr)
        raise
    finally:
        neon.close()
        render.close()

if __name__ == '__main__':
    main()
