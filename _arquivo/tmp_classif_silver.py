import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file(r'C:\teste\sapient-metrics.json')
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')
df = c.query("""
SELECT classificacao_1, COUNT(*) c
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
WHERE DATE(data_referencia) = DATE '2026-04-30'
GROUP BY 1 ORDER BY 1
""").to_dataframe()
print(df.to_string(index=False))
