"""Re-validação Alves x BQ APÓS re-extração + invoice_date."""
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

# 1) Metadata
print('=== METADATA pós re-extração ===')
df = c.query("""
SELECT
  MAX(loaded_at) AS ultima_extracao,
  MAX(order_date) AS ultimo_pedido,
  MAX(invoice_date) AS ultima_nota,
  COUNT(*) AS total_linhas,
  COUNTIF(invoice_date IS NOT NULL) AS linhas_com_nota
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
""").to_dataframe()
print(df.to_string(index=False))

# 2) Planilha Alves Maio/2026
df_alves = pd.read_excel(r'C:\Users\gusta\Downloads\Notas.xlsx')
df_alves = df_alves[(df_alves['ytipope']=='S') & (df_alves['ycodemp']==1)].copy()
print(f'\nPLANILHA ALVES: {len(df_alves)} notas / R$ {df_alves["yvaltot"].sum():,.2f}')
print(f'  Periodo (ydatnot): {df_alves["ydatnot"].min().date()} -> {df_alves["ydatnot"].max().date()}')

# 3) BQ por invoice_date (data NF — igual Alves)
print('\n=== BQ POR invoice_date (filtro <>N, status 4) — alinhado com Alves ===')
df_bq = c.query("""
SELECT
  COUNT(DISTINCT o.invoice_number) AS notas,
  COUNT(*) AS linhas,
  ROUND(SUM(o.total_amount), 2) AS faturamento
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
  ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
WHERE o.invoice_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND o.company_code = 1
""").to_dataframe()
print(df_bq.to_string(index=False))

# 4) Sem filtro de status
df_bq2 = c.query("""
SELECT
  COUNT(DISTINCT invoice_number) AS notas,
  ROUND(SUM(total_amount), 2) AS faturamento
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE invoice_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND company_code = 1
""").to_dataframe()
print('\n=== BQ POR invoice_date (sem filtro de status) ===')
print(df_bq2.to_string(index=False))

# 5) Diff de notas
print('\n=== DIFF NOTAS ===')
notas_alves = set(df_alves['ynumnot'].astype(int))
df_notas_bq = c.query("""
SELECT DISTINCT CAST(invoice_number AS INT64) AS nota
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE invoice_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND company_code = 1
""").to_dataframe()
notas_bq = set(df_notas_bq['nota'].dropna().astype(int))

so_alves = notas_alves - notas_bq
so_bq    = notas_bq - notas_alves
ambos    = notas_alves & notas_bq

print(f'  Notas ALVES:           {len(notas_alves)}')
print(f'  Notas BQ (invoice_date Maio):  {len(notas_bq)}')
print(f'  Match:                  {len(ambos)}  ({len(ambos)/len(notas_alves)*100:.1f}% do Alves)')
print(f'  Só no Alves:            {len(so_alves)}')
print(f'  Só no BQ:               {len(so_bq)}')

# 6) RESUMO COMPARATIVO
print('\n' + '=' * 80)
print('RESUMO COMPARATIVO FINAL')
print('=' * 80)
fat_alves = df_alves['yvaltot'].sum()
fat_bq_sem_status = df_bq2['faturamento'].iloc[0]
fat_bq_status4 = df_bq['faturamento'].iloc[0]
print(f'  Planilha Alves:                         R$ {fat_alves:,.2f}')
print(f'  BQ por invoice_date (sem filtro status):R$ {fat_bq_sem_status:,.2f}  ({fat_bq_sem_status/fat_alves*100:.1f}%)')
print(f'  BQ por invoice_date (status 4, <>N):    R$ {fat_bq_status4:,.2f}  ({fat_bq_status4/fat_alves*100:.1f}%)')
print(f'  Gap (sem status):   R$ {fat_alves - fat_bq_sem_status:+,.2f}')
print(f'  Gap (status 4):     R$ {fat_alves - fat_bq_status4:+,.2f}')

if so_alves:
    df_falt = df_alves[df_alves['ynumnot'].isin(so_alves)].copy()
    print(f'\n  Top 10 notas faltantes:')
    print(df_falt.nlargest(10, 'yvaltot')[['ynumnot','ydatnot','ynomcli','ycodnat','yvaltot']].to_string(index=False))
    print(f'  Total faltante: R$ {df_falt["yvaltot"].sum():,.2f}')
