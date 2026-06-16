"""Inspeciona schema e histórico das linhas Giovanna na param_com_rfv_carteira."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 200)
pd.set_option('display.max_colwidth', 80)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# Schema da carteira
print('=== SCHEMA param_com_rfv_carteira ===')
t = c.get_table('sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira')
for f in t.schema:
    print(f'  {f.name} {f.field_type}')

print(f'\nLast modified: {t.modified}')
print(f'Created: {t.created}')

# Conteúdo completo dos 7 Giovanna HOSPITALAR
print('\n=== Os 7 Giovanna HOSPITALAR — todas as colunas ===')
df = c.query("""
SELECT *
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
WHERE rfv_familia = 'HOSPITALAR'
  AND UPPER(salesperson_name) LIKE '%GIOVAN%'
""").to_dataframe()
print(df.to_string(index=False))

# Distribuição geral de vendedores na carteira
print('\n=== Distribuição de vendedores em toda a carteira ===')
dist = c.query("""
SELECT rfv_familia, salesperson_name, COUNT(*) AS n,
       SUM(CASE WHEN is_active THEN 1 ELSE 0 END) AS ativos
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
GROUP BY 1, 2
ORDER BY 1, n DESC
""").to_dataframe()
print(dist.to_string(index=False))
