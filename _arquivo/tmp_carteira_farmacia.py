"""Carteira FARMACIA — Farmers Farmacias (version 1)(Recuperado Automaticamente)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 70)

path = r'C:\Users\gusta\Downloads\Farmers Farmacias (version 1)(Recuperado Automaticamente) (3) (1).xlsx'
xls = pd.ExcelFile(path)

print('Abas:')
for s in xls.sheet_names:
    print(f'  - "{s}"')

for s in xls.sheet_names:
    df = pd.read_excel(path, sheet_name=s, header=None)
    print(f'\n=== "{s}" ({df.shape}) — primeiras 20 linhas (sem header) ===')
    print(df.head(20).to_string())
