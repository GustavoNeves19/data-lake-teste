import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r"C:\teste\sapient-metrics.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project="sapient-metrics-492914-m7")

# Busca descrição dos nature_codes relevantes para RFV HOSPITALAR
sql = """
SELECT
  n.nature_code,
  n.nature_name,
  n.direction,
  n.financial_flag,
  n.is_return,
  counts.clientes,
  counts.pedidos
FROM `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
JOIN (
  SELECT
    o.nature_code,
    COUNT(DISTINCT c.partner_code) AS clientes,
    COUNT(*) AS pedidos
  FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
  JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` c
    ON c.partner_code = o.partner_code
  WHERE c.rfv_familia = 'HOSPITALAR'
    AND c.is_active = TRUE
    AND o.order_status IN (3, 4)
    AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
  GROUP BY o.nature_code
) counts ON counts.nature_code = n.nature_code
ORDER BY counts.clientes DESC
"""
df = client.query(sql).to_dataframe()
print(df.to_string(index=False))
