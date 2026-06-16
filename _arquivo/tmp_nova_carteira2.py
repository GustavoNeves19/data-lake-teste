"""Explora estrutura completa da nova carteira."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 80)

path = r'C:\Users\gusta\Downloads\Carteira de Clientes - Inside Sales (Atualizado).xlsx'
df = pd.read_excel(path, sheet_name='Planilha1', header=None)

print(f'Shape: {df.shape}')
print()
print('=' * 90)
print('LINHAS 1-15 (descobrir cabeçalho)')
print('=' * 90)
print(df.head(15).to_string())

print()
print('=' * 90)
print('Valores únicos na coluna 0 (primeiras 80 não-vazias)')
print('=' * 90)
unique_col0 = df[0].dropna().astype(str).unique()
print(f'Total únicos: {len(unique_col0)}')
print(unique_col0[:80])

print()
print('=' * 90)
print('Coluna 9 (Farmácia) — valores únicos')
print('=' * 90)
unique_col9 = df[9].dropna().astype(str).unique()
print(f'Total únicos: {len(unique_col9)}')
print(unique_col9[:80])
