"""Valida: vendedor real (YCODVEN2 dominante) vs salesperson_name da carteira."""
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

# Para cada partner_code da carteira ATIVA, identifica vendedor dominante via YCODVEN2 (12 meses)
print('=== Carteira vs Vendedor real do ERP (12 meses) ===')
print()

q = """
WITH erp_vendedor AS (
  SELECT
    partner_code,
    salesperson_code AS ycodven2,
    salesperson_name AS vend_erp,
    COUNT(*) AS qtd_pedidos
  FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
  WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    AND order_status IN (3,4)
    AND salesperson_name IS NOT NULL
  GROUP BY 1,2,3
),
dominante AS (
  SELECT partner_code, ycodven2, vend_erp, qtd_pedidos,
         ROW_NUMBER() OVER (PARTITION BY partner_code ORDER BY qtd_pedidos DESC) AS rn
  FROM erp_vendedor
)
SELECT
  ca.partner_code,
  ca.partner_name,
  ca.rfv_familia,
  ca.salesperson_name AS vend_carteira,
  d.vend_erp        AS vend_erp_dominante,
  d.ycodven2        AS ycodven2,
  d.qtd_pedidos     AS ped_dominante,
  CASE
    WHEN d.vend_erp IS NULL THEN 'sem_vendas_erp'
    WHEN UPPER(ca.salesperson_name) = UPPER(d.vend_erp) THEN 'match'
    WHEN UPPER(ca.salesperson_name) LIKE CONCAT('%', SPLIT(UPPER(d.vend_erp), ' ')[OFFSET(0)], '%')
      OR UPPER(d.vend_erp) LIKE CONCAT('%', SPLIT(UPPER(ca.salesperson_name), ' ')[OFFSET(0)], '%')
    THEN 'match_parcial'
    ELSE 'DIVERGE'
  END AS status
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` ca
LEFT JOIN dominante d ON d.partner_code = ca.partner_code AND d.rn = 1
WHERE ca.is_active = TRUE
"""
df = c.query(q).to_dataframe()

print(f'Total clientes ativos na carteira: {len(df)}')
print()
print('Distribuicao do status:')
print(df['status'].value_counts().to_string())

print()
print('=== Por familia ===')
pivot = df.pivot_table(index='rfv_familia', columns='status', values='partner_code', aggfunc='count', fill_value=0)
print(pivot.to_string())

print()
print('=== Divergencias (vend_carteira != vend_erp) — amostra 30 ===')
div = df[df['status'] == 'DIVERGE'].copy()
print(f'Total divergencias: {len(div)}')
print()
print(div[['partner_code','partner_name','rfv_familia','vend_carteira','vend_erp_dominante','ped_dominante']].head(30).to_string(index=False))

print()
print('=== Especifico: Giovanna na carteira HOSPITALAR ===')
gi = df[(df['vend_carteira']=='Giovanna') & (df['rfv_familia']=='HOSPITALAR')]
print(gi[['partner_code','partner_name','vend_carteira','vend_erp_dominante','ped_dominante','status']].to_string(index=False))
