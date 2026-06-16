"""Valida: as 2.595 notas faltantes existem no BQ com OUTRA order_date?"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 50)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# Planilha Alves
df_alves = pd.read_excel(r'C:\Users\gusta\Downloads\Notas.xlsx')
df_alves = df_alves[(df_alves['ytipope']=='S') & (df_alves['ycodemp']==1)].copy()
print(f'Planilha Alves: {len(df_alves)} notas, R$ {df_alves["yvaltot"].sum():,.2f}')

# Pega TODAS as notas dessa lista no BQ, sem filtro de data
notas = sorted(df_alves['ynumnot'].astype(int).unique())
print(f'Numero de notas unicas Alves: {len(notas)}')

# BQ: busca essas notas sem filtro de data
# Vou usar chunks pra não estourar
all_bq = []
for i in range(0, len(notas), 1000):
    chunk = notas[i:i+1000]
    notas_str = ','.join(str(n) for n in chunk)
    df = c.query(f"""
    SELECT CAST(invoice_number AS INT64) AS nota,
           order_date,
           order_status,
           total_amount,
           nature_code
    FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
    WHERE invoice_number IN ({notas_str})
      AND company_code = 1
    """).to_dataframe()
    all_bq.append(df)
df_bq = pd.concat(all_bq, ignore_index=True)
print(f'\nDessas {len(notas)} notas, BQ tem {df_bq["nota"].nunique()} unicas, {len(df_bq)} linhas')

# Distribuicao por mes do order_date
df_bq['mes_pedido'] = pd.to_datetime(df_bq['order_date']).dt.to_period('M')
print('\nDistribuicao por mes do order_date:')
print(df_bq.groupby('mes_pedido')['nota'].nunique().to_string())

# E por status
print('\nDistribuicao por order_status:')
print(df_bq.groupby('order_status')['nota'].nunique().to_string())

# Hipotese: notas de Maio na planilha podem ter order_date em abril
# Vou pegar uma amostra das top 10 faltantes do script anterior
amostra = [96550, 96334, 96436, 96366, 96628, 96059, 96757, 96371, 96518, 96578]
print(f'\n=== Amostra 10 notas faltantes (top valor) — comparativo ===')
for n in amostra:
    alves = df_alves[df_alves['ynumnot'] == n].iloc[0]
    bq = df_bq[df_bq['nota'] == n]
    print(f'\nNota {n}:')
    print(f'  Alves: ydatnot={alves["ydatnot"].date()}, ycodnat={alves["ycodnat"]}, valor=R$ {alves["yvaltot"]:,.2f}')
    if bq.empty:
        print(f'  BQ:    NAO ENCONTRADA')
    else:
        for _, r in bq.iterrows():
            print(f'  BQ:    order_date={r["order_date"]}, status={r["order_status"]}, nat={r["nature_code"]}, valor=R$ {float(r["total_amount"]):,.2f}')

# Cobertura total: quantas notas Alves existem no BQ?
notas_alves = set(notas)
notas_bq = set(df_bq['nota'].dropna().astype(int))
print(f'\n=== COBERTURA ===')
print(f'  Notas Alves:              {len(notas_alves)}')
print(f'  Existem no BQ (qualquer data): {len(notas_alves & notas_bq)}  ({len(notas_alves & notas_bq)/len(notas_alves)*100:.1f}%)')
print(f'  NAO existem no BQ:        {len(notas_alves - notas_bq)}')
