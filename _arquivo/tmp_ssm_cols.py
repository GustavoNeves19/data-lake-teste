"""Lista colunas Y* das tabelas-chave."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni')

from extract.sqlserver import SQLServerExtractor

TABS = [
    'CLIENTES OU FORNECEDORES',
    'COMPRAS E VENDAS',
    'NATUREZAS DE OPERAÇÕES',
    'PAGAR E RECEBER',
]

with SQLServerExtractor() as ext:
    cur = ext._conn.cursor()
    for t in TABS:
        cur.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = N'{t}'
              AND COLUMN_NAME LIKE 'Y%'
            ORDER BY ORDINAL_POSITION
        """)
        rows = cur.fetchall()
        print(f'=== [{t}] — {len(rows)} colunas Y*')
        for r in rows:
            ln = f'({r.CHARACTER_MAXIMUM_LENGTH})' if r.CHARACTER_MAXIMUM_LENGTH else ''
            print(f'  {r.COLUMN_NAME:<14} {r.DATA_TYPE}{ln}')
        print()
