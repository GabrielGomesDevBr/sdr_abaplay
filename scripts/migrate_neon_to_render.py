"""
Script de migração: Neon → Render (schema sdr)
Lê dados do Neon via psycopg2 e gera arquivo SQL para importar via render psql.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import sys

import os
NEON_URL = os.environ["NEON_DATABASE_URL"]

def escape_sql(val):
    """Escapa valor para SQL"""
    if val is None:
        return 'NULL'
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, dict):
        val = json.dumps(val, ensure_ascii=False)
    s = str(val).replace("'", "''")
    return f"'{s}'"

def fetch_all(cur, table):
    cur.execute(f"SELECT * FROM {table}")
    return cur.fetchall()

def generate_insert(schema, table, rows, columns):
    """Gera INSERT statements para uma tabela"""
    if not rows:
        return ""
    
    lines = []
    lines.append(f"-- {table}: {len(rows)} rows")
    
    for row in rows:
        vals = []
        for col in columns:
            vals.append(escape_sql(row.get(col)))
        cols_str = ', '.join(columns)
        vals_str = ', '.join(vals)
        lines.append(f"INSERT INTO {schema}.{table} ({cols_str}) VALUES ({vals_str});")
    
    return '\n'.join(lines)

def main():
    print("Conectando ao Neon...", file=sys.stderr)
    conn = psycopg2.connect(NEON_URL, connect_timeout=15)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    output = []
    output.append("SET search_path TO sdr;")
    output.append("BEGIN;")
    output.append("")
    
    # 1. campaigns
    print("Exportando campaigns...", file=sys.stderr)
    rows = fetch_all(cur, 'campaigns')
    cols = ['id', 'name', 'region', 'description', 'created_at', 'updated_at', 'status', 'total_leads', 'emails_sent', 'emails_failed']
    output.append(generate_insert('sdr', 'campaigns', rows, cols))
    output.append("")
    
    # 2. leads
    print("Exportando leads...", file=sys.stderr)
    rows = fetch_all(cur, 'leads')
    cols = ['id', 'campaign_id', 'status', 'nome_clinica', 'endereco', 'cidade_uf', 'cnpj', 'site',
            'decisor_nome', 'decisor_cargo', 'decisor_linkedin', 'email_principal', 'email_tipo',
            'telefone', 'whatsapp', 'instagram', 'fonte', 'confianca', 'score',
            'resumo_clinica', 'perfil_decisor', 'gancho_personalizacao', 'dor_provavel', 'tom_sugerido',
            'notas', 'motivo_descarte', 'raw_data', 'created_at', 'updated_at']
    output.append(generate_insert('sdr', 'leads', rows, cols))
    output.append("")
    
    # 3. email_log
    print("Exportando email_log...", file=sys.stderr)
    rows = fetch_all(cur, 'email_log')
    cols = ['id', 'lead_id', 'campaign_id', 'email_to', 'subject', 'body_html', 'status',
            'attempt_number', 'resend_id', 'error_message', 'sent_at', 'created_at']
    output.append(generate_insert('sdr', 'email_log', rows, cols))
    output.append("")
    
    # 4. blacklist (sem domain, é GENERATED)
    print("Exportando blacklist...", file=sys.stderr)
    rows = fetch_all(cur, 'blacklist')
    cols = ['id', 'email', 'reason', 'source_campaign_id', 'added_at']
    output.append(generate_insert('sdr', 'blacklist', rows, cols))
    output.append("")
    
    # 5. email_events
    print("Exportando email_events...", file=sys.stderr)
    rows = fetch_all(cur, 'email_events')
    if rows:
        cols = ['email_log_id', 'event_type', 'payload', 'created_at']
        output.append(generate_insert('sdr', 'email_events', rows, cols))
        output.append("")
    else:
        output.append("-- email_events: 0 rows (vazia)")
        output.append("")
    
    # 6. settings
    print("Exportando settings...", file=sys.stderr)
    rows = fetch_all(cur, 'settings')
    cols = ['key', 'value', 'description', 'updated_at']
    output.append(generate_insert('sdr', 'settings', rows, cols))
    output.append("")
    
    output.append("COMMIT;")
    
    # Write to file
    sql = '\n'.join(output)
    with open('/tmp/neon_to_render_migration.sql', 'w') as f:
        f.write(sql)
    
    print(f"\nArquivo gerado: /tmp/neon_to_render_migration.sql", file=sys.stderr)
    print(f"Tamanho: {len(sql)} bytes", file=sys.stderr)
    
    cur.close()
    conn.close()
    print("Done!", file=sys.stderr)

if __name__ == '__main__':
    main()
