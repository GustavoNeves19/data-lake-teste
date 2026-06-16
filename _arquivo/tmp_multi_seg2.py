import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 220)
pd.set_option('display.max_colwidth', 70)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# Clientes em múltiplas famílias COM segmentos diferentes
print('Clientes em multiplas familias e com SEGMENTOS DIFERENTES por familia:')
df = c.query("""
WITH base AS (
  SELECT partner_name, rfv_familia, classificacao_2, valor_total, frequencia, recencia_dias
  FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
  WHERE DATE(data_referencia) = DATE '2026-04-30'
),
multi AS (
  SELECT partner_name
  FROM base
  GROUP BY 1
  HAVING COUNT(DISTINCT rfv_familia) > 1
     AND COUNT(DISTINCT classificacao_2) > 1
)
SELECT b.partner_name, b.rfv_familia, b.classificacao_2 AS segmento,
       b.frequencia, b.recencia_dias, ROUND(b.valor_total, 0) AS valor
FROM base b
JOIN multi m USING (partner_name)
ORDER BY b.partner_name, b.rfv_familia
""").to_dataframe()
print(f'Total: {df["partner_name"].nunique()} clientes')
print()
print(df.head(40).to_string(index=False))
