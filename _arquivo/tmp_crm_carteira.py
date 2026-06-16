"""Explora carteira no Pipedrive — owner de cada organization/person."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 220)
pd.set_option('display.max_colwidth', 60)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# Schemas
for table in ['dim_crm_user', 'dim_crm_organization', 'dim_crm_person']:
    print(f'\n=== Schema crm_raw.{table} ===')
    t = c.get_table(f'sapient-metrics-492914-m7.crm_raw.{table}')
    for f in t.schema[:30]:
        print(f'  {f.name} {f.field_type}')
    print(f'  total cols: {len(t.schema)}')

# Users
print('\n=== USERS (vendedores no Pipedrive) ===')
users = c.query("SELECT * FROM `sapient-metrics-492914-m7.crm_raw.dim_crm_user` ORDER BY 1").to_dataframe()
print(users.to_string(index=False))

# Distribuição por owner em organizations
print('\n=== Organizations por owner ===')
dist = c.query("""
SELECT
  o.owner_id,
  u.name AS owner_nome,
  COUNT(*) AS qtd_orgs
FROM `sapient-metrics-492914-m7.crm_raw.dim_crm_organization` o
LEFT JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_user` u ON u.user_id = o.owner_id
GROUP BY 1, 2
ORDER BY qtd_orgs DESC
""").to_dataframe()
print(dist.to_string(index=False))
