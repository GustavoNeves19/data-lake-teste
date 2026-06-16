"""Descobre nomes das tabelas-chave no NSR_ERP."""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni')

from extract.sqlserver import SQLServerExtractor

PATTERNS = ['CLIENTE', 'PARTNER', 'PESSOA', 'CADASTRO', 'PARCEIRO',
            'COMPRA', 'VENDA', 'PEDIDO', 'NATUREZA', 'OPERACAO',
            'RECEBER', 'TITULO', 'FINANCEIRO', 'COBRAN', 'PAGAR']

with SQLServerExtractor() as ext:
    cur = ext._conn.cursor()
    cur.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    all_tabs = [(r.TABLE_SCHEMA, r.TABLE_NAME) for r in cur.fetchall()]
    print(f'Total de tabelas no NSR_ERP: {len(all_tabs)}')
    print()
    for pat in PATTERNS:
        hits = [(s, t) for s, t in all_tabs if pat in t.upper()]
        if hits:
            print(f'=== {pat}:')
            for s, t in hits[:15]:
                print(f'  [{s}].[{t}]')
            print()
