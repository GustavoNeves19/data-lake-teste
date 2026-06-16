"""Compara faturamento Maio/2026 — planilha Alves x fact_sales_order do BQ."""
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

# 1) Planilha Alves — Maio/2026, empresa 1, ytipope=S
df_alves = pd.read_excel(r'C:\Users\gusta\Downloads\Notas.xlsx')
df_alves = df_alves[
    (df_alves['ytipope'] == 'S') &
    (df_alves['ycodemp'] == 1) &
    (df_alves['ydatnot'] >= '2026-05-01') &
    (df_alves['ydatnot'] <= '2026-05-25')
].copy()
print(f'PLANILHA ALVES (Maio/2026 ate dia 25, empresa 1, ytipope=S):')
print(f'  Notas: {len(df_alves)}')
print(f'  Faturamento (yvaltot): R$ {df_alves["yvaltot"].sum():,.2f}')
print(f'  Valor produto (yvalpro): R$ {df_alves["yvalpro"].sum():,.2f}')

# 2) BQ fact_sales_order — mesmo periodo + filtro <>N (como dashboard faz)
df_bq = c.query("""
SELECT
  COUNT(DISTINCT o.invoice_number) AS notas_unicas,
  COUNT(*) AS linhas,
  ROUND(SUM(o.total_amount), 2) AS faturamento_total
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
  ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
WHERE o.order_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND o.company_code = 1
  AND o.order_status IN (3, 4)
""").to_dataframe()
print(f'\nBQ fact_sales_order (mesmo periodo, filtro <>N, status 3/4):')
print(df_bq.to_string(index=False))

# 3) BQ sem filtro de status (tudo)
df_bq2 = c.query("""
SELECT
  COUNT(DISTINCT o.invoice_number) AS notas_unicas,
  COUNT(*) AS linhas,
  ROUND(SUM(o.total_amount), 2) AS faturamento_total
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
  ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
WHERE o.order_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND o.company_code = 1
""").to_dataframe()
print(f'\nBQ fact_sales_order (sem filtro de status):')
print(df_bq2.to_string(index=False))

# 4) Diferenças por nota — quais notas estao no Alves mas nao no BQ?
notas_alves = set(df_alves['ynumnot'].astype(int))
df_bq_notas = c.query("""
SELECT DISTINCT CAST(invoice_number AS INT64) AS nota
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE order_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND company_code = 1
  AND invoice_number IS NOT NULL
""").to_dataframe()
notas_bq = set(df_bq_notas['nota'].dropna().astype(int))

print(f'\n=== DIFF NOTAS ===')
print(f'  Notas só no Alves (faltam no BQ):  {len(notas_alves - notas_bq)}')
print(f'  Notas só no BQ (extras vs Alves):  {len(notas_bq - notas_alves)}')
print(f'  Em ambos:                          {len(notas_alves & notas_bq)}')

# Top notas faltantes
faltantes = notas_alves - notas_bq
if faltantes:
    df_falt = df_alves[df_alves['ynumnot'].isin(faltantes)].copy()
    print(f'\n  Top 10 notas faltantes (por valor):')
    print(df_falt.nlargest(10, 'yvaltot')[['ynumnot','ydatnot','ycodcli','ynomcli','ycodnat','yvaltot']].to_string(index=False))
    print(f'\n  Total perdido: R$ {df_falt["yvaltot"].sum():,.2f}')

extras = notas_bq - notas_alves
if extras:
    print(f'\n  {len(extras)} notas no BQ que nao estao no Alves — possivelmente outras empresas/ytipope')

# 5) Comparativo por código de natureza (Alves vs BQ)
print('\n=== POR CODIGO NATUREZA ===')
ag_alves = df_alves.groupby(df_alves['ycodnat'].astype(str).str.strip()).agg(
    valor_alves=('yvaltot', 'sum'),
    notas_alves=('ynumnot', 'count'),
).reset_index().rename(columns={'ycodnat': 'nature_code'})

ag_bq = c.query("""
SELECT
  nature_code,
  COUNT(DISTINCT invoice_number) AS notas_bq,
  ROUND(SUM(total_amount), 2) AS valor_bq
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE order_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
  AND company_code = 1
GROUP BY 1
""").to_dataframe()
ag_bq['nature_code'] = ag_bq['nature_code'].astype(str).str.strip()

cmp = ag_alves.merge(ag_bq, on='nature_code', how='outer').fillna(0)
cmp['diff_valor'] = cmp['valor_bq'] - cmp['valor_alves']
cmp = cmp.sort_values('valor_alves', ascending=False)
print(cmp.to_string(index=False))
print(f'\nTotal valor Alves: R$ {cmp["valor_alves"].sum():,.2f}')
print(f'Total valor BQ:    R$ {cmp["valor_bq"].sum():,.2f}')
print(f'Diferenca:         R$ {cmp["valor_bq"].sum() - cmp["valor_alves"].sum():+,.2f}')
