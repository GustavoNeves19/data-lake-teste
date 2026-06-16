"""Diagnostica por que a maioria dos 635 clientes HOSPITALAR não aparece no silver."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r"C:\teste\sapient-metrics.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project="sapient-metrics-492914-m7")

proj = "sapient-metrics-492914-m7"

# 1. Quantos partner_codes HOSPITALAR na carteira têm pelo menos 1 pedido na janela?
sql1 = f"""
SELECT
  'Na carteira (HOSPITALAR)'            AS origem,
  COUNT(DISTINCT c.partner_code)        AS total
FROM `{proj}.silver_comercial.param_com_rfv_carteira` c
WHERE c.rfv_familia = 'HOSPITALAR' AND c.is_active = TRUE

UNION ALL

SELECT
  'Com pedido nos últimos 13m (5101A/6101A)' AS origem,
  COUNT(DISTINCT c.partner_code)
FROM `{proj}.silver_comercial.param_com_rfv_carteira` c
JOIN `{proj}.dm_orders.fact_sales_order` o
  ON o.partner_code = c.partner_code
WHERE c.rfv_familia = 'HOSPITALAR'
  AND c.is_active = TRUE
  AND o.order_status IN (3, 4)
  AND o.nature_code IN ('5101  A', '6101  A')
  AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)

UNION ALL

SELECT
  'Com pedido nos últimos 13m (QUALQUER nature)' AS origem,
  COUNT(DISTINCT c.partner_code)
FROM `{proj}.silver_comercial.param_com_rfv_carteira` c
JOIN `{proj}.dm_orders.fact_sales_order` o
  ON o.partner_code = c.partner_code
WHERE c.rfv_familia = 'HOSPITALAR'
  AND c.is_active = TRUE
  AND o.order_status IN (3, 4)
  AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)

UNION ALL

SELECT
  'Com QUALQUER pedido no ERP (sem filtro data)' AS origem,
  COUNT(DISTINCT c.partner_code)
FROM `{proj}.silver_comercial.param_com_rfv_carteira` c
JOIN `{proj}.dm_orders.fact_sales_order` o
  ON o.partner_code = c.partner_code
WHERE c.rfv_familia = 'HOSPITALAR'
  AND c.is_active = TRUE
"""
df1 = client.query(sql1).to_dataframe()
print("=== HOSPITALAR — Funil de filtros ===")
print(df1.to_string(index=False))

# 2. Distribuição dos pedidos por nature_code para HOSPITALAR
sql2 = f"""
SELECT
  o.nature_code,
  COUNT(DISTINCT o.partner_code) AS clientes,
  COUNT(*) AS pedidos
FROM `{proj}.dm_orders.fact_sales_order` o
JOIN `{proj}.silver_comercial.param_com_rfv_carteira` c
  ON c.partner_code = o.partner_code
WHERE c.rfv_familia = 'HOSPITALAR'
  AND c.is_active = TRUE
  AND o.order_status IN (3, 4)
  AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
GROUP BY o.nature_code
ORDER BY clientes DESC
LIMIT 15
"""
df2 = client.query(sql2).to_dataframe()
print("\n=== Nature codes presentes (últimos 13m, status 3/4) ===")
print(df2.to_string(index=False))
