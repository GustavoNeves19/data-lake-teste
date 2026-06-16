"""Carteira de Clientes - Inside Sales (Atualizado) — exploração."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

pd.set_option('display.width', 220)
pd.set_option('display.max_colwidth', 70)

path = r'C:\Users\gusta\Downloads\Carteira de Clientes - Inside Sales (Atualizado).xlsx'
xls = pd.ExcelFile(path)

print('=' * 90)
print('ABAS DO ARQUIVO')
print('=' * 90)
for s in xls.sheet_names:
    print(f'  - "{s}"')

print('\n' + '=' * 90)
print('AMOSTRA DE CADA ABA (primeiras 8 linhas)')
print('=' * 90)
for s in xls.sheet_names:
    df = pd.read_excel(path, sheet_name=s)
    print(f'\n--- "{s}" ({len(df)} linhas, {len(df.columns)} colunas) ---')
    print(f'  Colunas: {list(df.columns)}')
    print(df.head(8).to_string(index=False))
