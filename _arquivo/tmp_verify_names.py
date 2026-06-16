import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform'])
client = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

CODES = [23624, 22570, 23006, 31599, 913644, 300192, 23535, 32063]
codes_str = ', '.join(str(c) for c in CODES)

sql = f"""
SELECT c.partner_code, s.partner_name, s.rfv_familia, s.classificacao_2 AS segmento
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score` s
JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` c
  ON c.partner_name = s.partner_name AND c.rfv_familia = s.rfv_familia
WHERE c.partner_code IN ({codes_str})
ORDER BY s.rfv_familia, s.partner_name
"""
df = client.query(sql).to_dataframe()
print("Nomes que antes tinham '?' — agora corretos:")
print(f"{'Código':<10} {'Nome':<55} {'Família':<12} {'Segmento'}")
print(f"{'─'*10} {'─'*55} {'─'*12} {'─'*20}")
for _, r in df.iterrows():
    print(f"{int(r['partner_code']):<10} {str(r['partner_name']):<55} {r['rfv_familia']:<12} {r['segmento']}")
