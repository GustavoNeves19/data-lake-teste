"""Verifica nomes corrompidos na carteira e no silver_com_rfv_score."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform'])
client = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

print("1. Nomes corrompidos por família na CARTEIRA")
sql = """
SELECT rfv_familia,
  COUNT(*) AS total,
  COUNTIF(partner_name LIKE '%?%') AS corrompidos,
  ROUND(COUNTIF(partner_name LIKE '%?%') / COUNT(*) * 100, 1) AS pct
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
GROUP BY rfv_familia ORDER BY rfv_familia
"""
for _, r in client.query(sql).to_dataframe().iterrows():
    print(f"   {r['rfv_familia']}: {int(r['corrompidos'])}/{int(r['total'])} ({float(r['pct'])}%) corrompidos")

print()
print("2. Nomes corrompidos por família no SILVER_RFV_SCORE")
sql2 = """
SELECT rfv_familia,
  COUNT(*) AS total,
  COUNTIF(partner_name LIKE '%?%') AS corrompidos
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
GROUP BY rfv_familia ORDER BY rfv_familia
"""
try:
    for _, r in client.query(sql2).to_dataframe().iterrows():
        print(f"   {r['rfv_familia']}: {int(r['corrompidos'])}/{int(r['total'])} corrompidos")
except Exception as e:
    print(f"   {e}")

print()
print("3. Amostra de nomes corrompidos na carteira")
sql3 = """
SELECT partner_code, partner_name, rfv_familia
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
WHERE partner_name LIKE '%?%'
ORDER BY rfv_familia, partner_name
LIMIT 20
"""
for _, r in client.query(sql3).to_dataframe().iterrows():
    print(f"   [{int(r['partner_code'])}] {r['rfv_familia']} | {r['partner_name']}")
