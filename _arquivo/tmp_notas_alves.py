"""Explora a planilha de Notas do Alves — validar codigos de natureza."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)
pd.set_option('display.max_columns', 50)

path = r'C:\Users\gusta\Downloads\Notas.xlsx'
xls = pd.ExcelFile(path)

print('Abas:')
for s in xls.sheet_names:
    print(f'  - "{s}"')

for s in xls.sheet_names:
    df = pd.read_excel(path, sheet_name=s)
    print(f'\n=== "{s}" ({df.shape[0]} linhas, {df.shape[1]} colunas) ===')
    print(f'Colunas: {list(df.columns)}')
    print('\nPrimeiras 10 linhas:')
    print(df.head(10).to_string(index=False))
    print('\nTipos:')
    print(df.dtypes.to_string())
