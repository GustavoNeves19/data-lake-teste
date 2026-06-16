"""Cruza Notas.xlsx (Alves) com dim_operation_nature do BQ — valida filtro <>'N'."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# 1) Carrega notas
df = pd.read_excel(r'C:\Users\gusta\Downloads\Notas.xlsx')
print(f'Total notas: {len(df)}')
print(f'Período: {df["ydatnot"].min()} → {df["ydatnot"].max()}')
print(f'Tipos ytipope: {df["ytipope"].value_counts().to_dict()}')
print(f'Empresas (ycodemp): {df["ycodemp"].value_counts().to_dict()}')

# Filtrar só ytipope='S' (saída/venda) — alinha com nosso fact_sales_order
df_s = df[df['ytipope'] == 'S'].copy()
print(f'\nApós filtro ytipope=S: {len(df_s)} linhas')

# 2) Lista naturezas únicas
naturezas = df_s['ycodnat'].astype(str).str.strip().unique()
print(f'\nNaturezas únicas usadas: {len(naturezas)}')
print(sorted(naturezas))

# 3) Cruza com dim_operation_nature do BQ pra ver as flags
naturezas_list = ','.join(f"'{n}'" for n in naturezas)
df_nat = c.query(f"""
SELECT nature_code, nature_name, financial_flag, stock_movement_type, is_return
FROM `sapient-metrics-492914-m7.dm_orders.dim_operation_nature`
WHERE nature_code IN ({naturezas_list})
ORDER BY financial_flag, nature_code
""").to_dataframe()

# 4) Agrega faturamento por natureza × flag
ag = df_s.groupby(df_s['ycodnat'].astype(str).str.strip()).agg(
    qtd_notas=('ynumnot', 'count'),
    valor=('yvaltot', 'sum'),
).reset_index().rename(columns={'ycodnat': 'nature_code'})

merged = ag.merge(df_nat, on='nature_code', how='left')
merged = merged.sort_values('valor', ascending=False)

print('\n' + '=' * 110)
print('CRUZAMENTO: Notas do Alves × dim_operation_nature do BQ')
print('=' * 110)
print(merged.to_string(index=False))

# 5) Análise: o que entraria no nosso filtro <>'N' vs o que ficaria fora
print('\n' + '=' * 110)
print('IMPACTO DO FILTRO financial_flag <> N (nosso filtro atual)')
print('=' * 110)
sem_match = merged[merged['financial_flag'].isna()]
com_flag_n = merged[merged['financial_flag'] == 'N']
demais = merged[merged['financial_flag'].notna() & (merged['financial_flag'] != 'N')]

print(f'\nNATUREZAS SEM MATCH NA DIM: {len(sem_match)}  (PROBLEMA: ficam fora do filtro)')
if len(sem_match):
    print(sem_match[['nature_code','qtd_notas','valor']].to_string(index=False))
    print(f'  Faturamento perdido: R$ {sem_match["valor"].sum():,.2f}')

print(f'\nNATUREZAS COM flag = N: {len(com_flag_n)}  (EXCLUÍDAS pelo nosso filtro)')
if len(com_flag_n):
    print(com_flag_n[['nature_code','nature_name','qtd_notas','valor']].to_string(index=False))
    print(f'  Faturamento excluído: R$ {com_flag_n["valor"].sum():,.2f}')

print(f'\nNATUREZAS COM flag != N: {len(demais)}  (INCLUÍDAS pelo nosso filtro) ✓')
print(f'  Faturamento incluído: R$ {demais["valor"].sum():,.2f}')

print('\n' + '=' * 110)
print('RESUMO FINAL')
print('=' * 110)
fat_total = df_s['yvaltot'].sum()
fat_inc = demais['valor'].sum()
fat_n = com_flag_n['valor'].sum()
fat_null = sem_match['valor'].sum()
print(f'Faturamento total nota Alves:  R$ {fat_total:,.2f} ({len(df_s)} notas)')
print(f'  Incluído (<>N):              R$ {fat_inc:,.2f} ({fat_inc/fat_total*100:.1f}%)')
print(f'  Excluído (flag=N):           R$ {fat_n:,.2f} ({fat_n/fat_total*100:.1f}%)')
print(f'  Sem flag (PROBLEMA):         R$ {fat_null:,.2f} ({fat_null/fat_total*100:.1f}%)')
