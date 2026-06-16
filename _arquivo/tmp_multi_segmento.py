"""Pode um cliente ter mais de um segmento RFV?"""
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

# 1) Existe cliente com mais de UM segmento na MESMA data_referencia?
print('=' * 80)
print('1) Clientes com >1 segmento numa MESMA data_referencia')
print('=' * 80)
df = c.query("""
SELECT
  partner_name,
  data_referencia,
  COUNT(DISTINCT classificacao_2) AS qtd_segmentos,
  STRING_AGG(DISTINCT classificacao_2, ' | ') AS segmentos,
  STRING_AGG(DISTINCT rfv_familia, ' | ') AS familias
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
WHERE DATE(data_referencia) = DATE '2026-04-30'
GROUP BY 1, 2
HAVING COUNT(DISTINCT classificacao_2) > 1
ORDER BY qtd_segmentos DESC, partner_name
""").to_dataframe()
print(f'\nTotal clientes com >1 segmento: {len(df)}')
print()
if not df.empty:
    print(df.head(20).to_string(index=False))

# 2) E clientes em múltiplas FAMÍLIAS?
print('\n' + '=' * 80)
print('2) Clientes em mais de UMA família')
print('=' * 80)
df2 = c.query("""
SELECT
  partner_name,
  COUNT(DISTINCT rfv_familia) AS qtd_familias,
  STRING_AGG(DISTINCT rfv_familia, ' | ') AS familias,
  STRING_AGG(DISTINCT classificacao_2, ' | ') AS segmentos
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
WHERE DATE(data_referencia) = DATE '2026-04-30'
GROUP BY 1
HAVING qtd_familias > 1
ORDER BY qtd_familias DESC, partner_name
""").to_dataframe()
print(f'\nTotal clientes em multiplas familias: {len(df2)}')
print()
if not df2.empty:
    print(df2.head(20).to_string(index=False))

# 3) Resumo por número de segmentos
print('\n' + '=' * 80)
print('3) Distribuicao — quantos clientes tem X segmentos?')
print('=' * 80)
df3 = c.query("""
WITH base AS (
  SELECT
    partner_name,
    COUNT(DISTINCT classificacao_2) AS qtd_segs
  FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
  WHERE DATE(data_referencia) = DATE '2026-04-30'
  GROUP BY 1
)
SELECT qtd_segs, COUNT(*) AS clientes
FROM base GROUP BY 1 ORDER BY 1
""").to_dataframe()
print(df3.to_string(index=False))
