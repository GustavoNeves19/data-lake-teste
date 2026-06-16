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
  classificacao_2                        AS segmento,
  classificacao_3                        AS ordem,
  COUNT(DISTINCT partner_name)           AS clientes,
  ROUND(SUM(valor_total), 2)             AS faturamento,
  ROUND(AVG(frequencia), 1)              AS freq_media,
  ROUND(AVG(recencia_dias), 0)           AS rec_media_dias,
  MIN(data_referencia)                   AS data_ref
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
GROUP BY rfv_familia, classificacao_2, classificacao_3
ORDER BY rfv_familia, classificacao_3
"""
df = client.query(sql).to_dataframe()

for familia in ["HOSPITALAR", "FARMACIAS", "SAC"]:
    sub = df[df["rfv_familia"] == familia].copy()
    total_cli = int(sub["clientes"].sum())
    total_fat = float(sub["faturamento"].sum())
    data_ref  = str(sub["data_ref"].iloc[0]) if not sub.empty else "?"
    print(f"{'='*68}")
    print(f"  {familia}  |  Ref: {data_ref}  |  {total_cli} clientes  |  R$ {total_fat:,.2f}")
    print(f"{'='*68}")
    print(f"  {'Segmento':<25} {'Clientes':>8}  {'Faturamento':>15}  {'F.Méd':>6}  {'R.Méd(d)':>8}")
    print(f"  {'-'*25} {'-'*8}  {'-'*15}  {'-'*6}  {'-'*8}")
    for _, r in sub.iterrows():
        fat_str = f"R$ {float(r['faturamento']):>12,.2f}"
        print(f"  {r['segmento']:<25} {int(r['clientes']):>8}  {fat_str}  {float(r['freq_media']):>6.1f}  {int(r['rec_media_dias']):>8}")
    print()
