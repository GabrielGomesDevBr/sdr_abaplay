"""
Script de migração: Adiciona colunas do contexto_abordagem na planilha leads
Preserva todos os dados existentes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_worksheet, SHEET_COLUMNS

def migrate_leads_sheet():
    """
    Migra a planilha leads para incluir as novas colunas do contexto_abordagem.
    
    Novas colunas (inseridas após 'score'):
    - resumo_clinica
    - perfil_decisor
    - gancho_personalizacao
    - dor_provavel
    - tom_sugerido
    """
    print("🔄 Iniciando migração da planilha 'leads'...")
    
    ws = get_worksheet('leads')
    
    # Busca cabeçalho atual
    current_header = ws.row_values(1)
    print(f"📊 Cabeçalho atual: {current_header}")
    print(f"   Total de colunas: {len(current_header)}")
    
    # Novas colunas esperadas
    new_columns = ['resumo_clinica', 'perfil_decisor', 'gancho_personalizacao', 'dor_provavel', 'tom_sugerido']
    
    # Verifica se as colunas já existem
    missing_columns = [col for col in new_columns if col not in current_header]
    
    if not missing_columns:
        print("✅ Todas as novas colunas já existem! Nenhuma migração necessária.")
        return
    
    print(f"📝 Colunas a adicionar: {missing_columns}")
    
    # Busca todos os dados
    all_data = ws.get_all_values()
    print(f"📄 Total de linhas (incluindo cabeçalho): {len(all_data)}")
    
    if len(all_data) <= 1:
        # Apenas cabeçalho, atualiza direto
        print("🔧 Planilha vazia, atualizando apenas cabeçalho...")
        ws.update('A1', [SHEET_COLUMNS['leads']])
        print("✅ Cabeçalho atualizado!")
        return
    
    # Encontra a posição de inserção (após 'score')
    try:
        score_index = current_header.index('score')
        insert_position = score_index + 1
    except ValueError:
        # Se não encontrar 'score', insere antes de 'raw_data'
        try:
            insert_position = current_header.index('raw_data')
        except ValueError:
            insert_position = len(current_header) - 1
    
    print(f"📍 Posição de inserção: coluna {insert_position + 1}")
    
    # Prepara novos dados
    new_data = []
    
    for i, row in enumerate(all_data):
        # Garante que a linha tenha o tamanho correto
        row = list(row)
        while len(row) < len(current_header):
            row.append('')
        
        if i == 0:
            # Cabeçalho - insere novas colunas
            new_row = row[:insert_position] + new_columns + row[insert_position:]
        else:
            # Dados - insere células vazias para as novas colunas
            new_row = row[:insert_position] + [''] * len(new_columns) + row[insert_position:]
        
        new_data.append(new_row)
    
    print(f"📊 Novo cabeçalho terá {len(new_data[0])} colunas")
    
    # Limpa a planilha e reescreve
    print("🧹 Limpando planilha...")
    ws.clear()
    
    print("📝 Escrevendo dados migrados...")
    # Escreve em batches para evitar timeout
    batch_size = 100
    for i in range(0, len(new_data), batch_size):
        batch = new_data[i:i + batch_size]
        start_row = i + 1
        end_row = start_row + len(batch) - 1
        
        # Calcula o range
        end_col = chr(ord('A') + len(new_data[0]) - 1) if len(new_data[0]) <= 26 else 'Z'
        range_str = f"A{start_row}:{end_col}{end_row}"
        
        ws.update(range_str, batch)
        print(f"   ✓ Linhas {start_row}-{end_row} escritas")
    
    print("✅ Migração concluída com sucesso!")
    print(f"📊 Novo cabeçalho: {new_data[0]}")


if __name__ == "__main__":
    migrate_leads_sheet()
