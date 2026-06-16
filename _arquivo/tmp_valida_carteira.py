import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r"C:\teste\sapient-metrics.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project="sapient-metrics-492914-m7")

sql = """
SELECT
  rfv_familia,
  COUNT(DISTINCT partner_name)  AS clientes_unicos,
  ROUND(SUM(valor_total), 0)    AS faturamento_total,
  COUNTIF(freq_bucket = 'F1' AND rec_bucket = 'R1') AS campeoes,
  COUNTIF(rec_bucket = 'R5')    AS perdidos,
  COUNTIF(rec_bucket IN ('R4','R5') AND freq_bucket IN ('F1','F2')) AS em_risco
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
GROUP BY rfv_familia
ORDER BY rfv_familia
"""
df = client.query(sql).to_dataframe()
print(df.to_string(index=False))

total = client.query(
    "SELECT COUNT(DISTINCT partner_name) AS total FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`"
).to_dataframe().iloc[0, 0]
print(f"\nTOTAL geral: {total} clientes únicos")
