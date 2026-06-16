"""Lista clientes da Giovanna na param_com_rfv_carteira."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

q = """
SELECT
  ca.partner_code,
  ca.partner_name,
  ca.rfv_familia,
  ca.salesperson_name,
  ca.is_active,
  COUNT(DISTINCT o.order_number) AS qtd_pedidos_12m,
  ROUND(SUM(o.total_amount), 2) AS faturamento_12m
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` ca
LEFT JOIN `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
  ON o.partner_code = ca.partner_code
  AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
  AND o.order_status IN (3,4)
WHERE UPPER(ca.salesperson_name) LIKE '%GIOVAN%'
GROUP BY 1,2,3,4,5
ORDER BY ca.rfv_familia, ca.partner_name
"""
df = c.query(q).to_dataframe()
print(df.to_string(index=False))
print()
print(f'TOTAL: {len(df)} clientes na carteira da Giovanna')
print()
print('Por familia:')
print(df.groupby(['rfv_familia','is_active']).size().to_string())
