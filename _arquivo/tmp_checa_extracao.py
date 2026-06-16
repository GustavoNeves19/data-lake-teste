"""Verifica recência do fact_sales_order + onde estão as 567 notas faltantes."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 240)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# 1) Quando foi a ultima extracao + ultima nota
print('=== METADATA ===')
df = c.query("""
SELECT
  MAX(loaded_at) AS ultima_extracao,
  MAX(order_date) AS ultimo_pedido_data,
  MAX(invoice_number) AS maior_invoice,
  COUNT(*) AS total_linhas
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
""").to_dataframe()
print(df.to_string(index=False))

# 2) Pega uma nota especifica que esta faltando (96550 - LHVMED R$ 86k)
# Procura pelo partner_code + valor proximo
print('\n=== Procurando nota 96550 (LHVMED, R$ 86k, ydatnot=20/05) ===')
df2 = c.query("""
SELECT order_number, invoice_number, partner_code, order_date, order_status,
       total_amount, nature_code
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE partner_code = 46561
  AND order_date >= '2026-04-01'
ORDER BY order_date DESC
LIMIT 20
""").to_dataframe()
print(df2.to_string(index=False))

# 3) Verifica se as notas faltantes existem como NULL invoice_number
print('\n=== Pedidos com invoice_number NULL nas ultimas 4 semanas ===')
df3 = c.query("""
SELECT
  COUNT(*) AS pedidos_sem_nota,
  COUNT(DISTINCT order_number) AS distinct_orders,
  ROUND(SUM(total_amount), 2) AS valor_total
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE order_date >= '2026-05-01'
  AND invoice_number IS NULL
""").to_dataframe()
print(df3.to_string(index=False))

# 4) Quantos pedidos por order_status (entender o que e 0 vs 4)
print('\n=== Distribuicao por order_status (Maio/2026) ===')
df4 = c.query("""
SELECT order_status, COUNT(*) AS qtd,
       ROUND(SUM(total_amount), 2) AS valor
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE order_date BETWEEN '2026-05-01' AND '2026-05-25'
GROUP BY 1 ORDER BY 1
""").to_dataframe()
print(df4.to_string(index=False))
