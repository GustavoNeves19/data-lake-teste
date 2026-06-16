"""Lê a base completa de clientes da nova carteira."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)

path = r'C:\Users\gusta\Downloads\Carteira de Clientes - Inside Sales (Atualizado).xlsx'

# Linha 14 (idx 14) = cabeçalho, dados começam na 15
df = pd.read_excel(path, sheet_name='Planilha1', header=14)
df = df.rename(columns={c: c.strip() if isinstance(c, str) else c for c in df.columns})

print(f'Shape: {df.shape}')
print(f'\nColunas: {list(df.columns)}')
print()
print('Primeiras 10 linhas:')
print(df.head(10).to_string(index=False))

print('\n' + '=' * 80)
print('Distribuicao por VENDEDOR RESPONSAVEL')
print('=' * 80)
dist_vend = df['Vendedor Responsável'].value_counts(dropna=False)
print(dist_vend.to_string())

print('\n' + '=' * 80)
print('Distribuicao por TIPO DE VENDA')
print('=' * 80)
dist_tipo = df['Tipo de venda'].value_counts(dropna=False)
print(dist_tipo.to_string())

print('\n' + '=' * 80)
print('CROSSTAB: Vendedor x Tipo de venda')
print('=' * 80)
ct = pd.crosstab(df['Vendedor Responsável'].fillna('SEM_VEND'), df['Tipo de venda'].fillna('SEM_TIPO'), margins=True, margins_name='TOTAL')
print(ct.to_string())

# Cobertura: tem ID CRM? tem ID ERP?
print('\n' + '=' * 80)
print('Cobertura de IDs')
print('=' * 80)
print(f'Total clientes:     {len(df)}')
print(f'  Com ID CRM:       {df["ID CRM"].notna().sum()} ({df["ID CRM"].notna().mean()*100:.1f}%)')
print(f'  Com ID ERP:       {df["ID ERP"].notna().sum()} ({df["ID ERP"].notna().mean()*100:.1f}%)')
print(f'  Com CNPJ:         {df["CNPJ"].notna().sum()} ({df["CNPJ"].notna().mean()*100:.1f}%)')
print(f'  Com vendedor:     {df["Vendedor Responsável"].notna().sum()} ({df["Vendedor Responsável"].notna().mean()*100:.1f}%)')

# Salva CSV limpo
out = r'C:\Users\gusta\Downloads\carteira_nova_processada.csv'
df.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\nCSV salvo: {out}')
