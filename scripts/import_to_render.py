"""
Splits the migration SQL into per-table files and imports via render psql.
"""
import subprocess
import sys
import os

SQL_FILE = '/tmp/neon_to_render_migration.sql'
DB_ID = 'dpg-d07n3madbo4c73ehoiqg-a'

def split_sql():
    """Split SQL file into table sections"""
    with open(SQL_FILE, 'r') as f:
        lines = f.readlines()
    
    # Find section boundaries
    sections = {}
    current_table = None
    current_lines = []
    
    for line in lines:
        if line.startswith('-- campaigns:'):
            current_table = 'campaigns'
            current_lines = []
        elif line.startswith('-- leads:'):
            if current_table:
                sections[current_table] = current_lines
            current_table = 'leads'
            current_lines = []
        elif line.startswith('-- email_log:'):
            if current_table:
                sections[current_table] = current_lines
            current_table = 'email_log'
            current_lines = []
        elif line.startswith('-- blacklist:'):
            if current_table:
                sections[current_table] = current_lines
            current_table = 'blacklist'
            current_lines = []
        elif line.startswith('-- email_events:'):
            if current_table:
                sections[current_table] = current_lines
            current_table = 'email_events'
            current_lines = []
        elif line.startswith('-- settings:'):
            if current_table:
                sections[current_table] = current_lines
            current_table = 'settings'
            current_lines = []
        elif line.strip() in ('COMMIT;', ''):
            pass
        
        if current_table and line.startswith('INSERT'):
            current_lines.append(line)
    
    if current_table:
        sections[current_table] = current_lines
    
    return sections

def run_sql_safely(sql):
    """Execute via render psql -c directly avoiding shell quoting issues"""
    try:
        result = subprocess.run(
            ['render', 'psql', DB_ID, '-c', sql],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return False, result.stderr
        return True, ""
    except OSError as e:
        if e.errno == 7:  # Argument list too long
            return False, "ARG_MAX"
        raise

def import_section(table, lines):
    """Import a section via render psql"""
    if not lines:
        print(f"  {table}: 0 rows (skip)")
        return True
    
    # Split into chunks (small enough for shell argument limit)
    chunk_size = 25 if table in ('leads', 'email_log') else 100
    chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]
    print(f"  {table}: {len(lines)} rows in {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks):
        # Add ON CONFLICT DO NOTHING to avoid errors on rows already imported
        safe_lines = [
            line.rstrip(';\n') + ' ON CONFLICT DO NOTHING;\n' if line.startswith('INSERT') else line
            for line in chunk
        ]
        sql = f"SET search_path TO sdr;\n" + ''.join(safe_lines)

        ok, err = run_sql_safely(sql)
        if not ok:
            # Try even smaller chunks
            sub_size = 5
            sub_chunks = [safe_lines[j:j+sub_size] for j in range(0, len(safe_lines), sub_size)]
            for si, sub in enumerate(sub_chunks):
                sub_sql = f"SET search_path TO sdr;\n" + ''.join(sub)
                ok2, err2 = run_sql_safely(sub_sql)
                if not ok2:
                    print(f"  ERROR chunk {i}.{si}: {err2[:200]}")
                    return False
            print(f"    chunk {i+1}/{len(chunks)}: OK ({len(chunk)} rows, sub-chunked)")
        else:
            print(f"    chunk {i+1}/{len(chunks)}: OK ({len(chunk)} rows)")
    return True

def main():
    print("Splitting SQL file...")
    sections = split_sql()
    
    for table, lines in sections.items():
        print(f"\nFound: {table} = {len(lines)} rows")
    
    # Import in order (respecting FKs) — campaigns and leads already imported
    order = ['email_log', 'blacklist', 'email_events', 'settings']
    
    print("\n=== Importing ===")
    for table in order:
        lines = sections.get(table, [])
        ok = import_section(table, lines)
        if not ok:
            print(f"FAILED at {table}. Stopping.")
            sys.exit(1)
    
    print("\n=== DONE! ===")

if __name__ == '__main__':
    main()
