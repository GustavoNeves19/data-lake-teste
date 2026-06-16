"""
Corrige partner_name corrompido em dm_partners.dim_partner usando
o org_name do Pipedrive (via param_com_entity_bridge).

Lógica:
  1. dim_partner WHERE partner_name LIKE '%?%'
  2. JOIN param_com_entity_bridge ON partner_code
  3. org_name = nome limpo do Pipedrive (sempre sem '?')
  4. UPDATE dim_partner SET partner_name = org_name, legal_name = org_name

Depois faz o mesmo para param_com_entity_bridge.partner_name.
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

PROJ     = "sapient-metrics-492914-m7"
CREDS_BQ = r"C:\teste\sapient-metrics.json"

creds = service_account.Credentials.from_service_account_file(
    CREDS_BQ, scopes=["https://www.googleapis.com/auth/cloud-platform"])
client = bigquery.Client(credentials=creds, project=PROJ)

# ── 1. Diagnóstico de cobertura ────────────────────────────────────────────────
print("=" * 72)
print("  COBERTURA: parceiros corrompidos vs mapeados no Pipedrive")
print("=" * 72)

sql_cov = f"""
SELECT
  COUNT(*)                                        AS total_corrompidos,
  COUNTIF(e.org_name IS NOT NULL
    AND e.org_name NOT LIKE '%?%')                AS com_pipedrive,
  COUNTIF(e.org_name IS NULL
    OR  e.org_name LIKE '%?%')                    AS sem_pipedrive,
  ROUND(COUNTIF(e.org_name IS NOT NULL
    AND e.org_name NOT LIKE '%?%')
    / COUNT(*) * 100, 1)                          AS pct_cobertura
FROM `{PROJ}.dm_partners.dim_partner` d
LEFT JOIN `{PROJ}.silver_comercial.param_com_entity_bridge` e
  ON e.partner_code = d.partner_code
WHERE d.partner_name LIKE '%?%'
"""
r = client.query(sql_cov).to_dataframe().iloc[0]
print(f"  Corrompidos totais:         {int(r['total_corrompidos'])}")
print(f"  Com nome limpo (Pipedrive): {int(r['com_pipedrive'])}  ({float(r['pct_cobertura'])}% de cobertura)")
print(f"  Sem Pipedrive:              {int(r['sem_pipedrive'])}  (nomes próprios / pessoa física)")

# ── 2. Amostra dos que serão corrigidos ───────────────────────────────────────
print()
print("  Amostra — será corrigido:")
sql_sample = f"""
SELECT d.partner_code, d.partner_name AS nome_erp, e.org_name AS nome_pipedrive
FROM `{PROJ}.dm_partners.dim_partner` d
JOIN `{PROJ}.silver_comercial.param_com_entity_bridge` e
  ON e.partner_code = d.partner_code
WHERE d.partner_name LIKE '%?%'
  AND e.org_name NOT LIKE '%?%'
ORDER BY d.partner_name
LIMIT 15
"""
for _, r in client.query(sql_sample).to_dataframe().iterrows():
    print(f"  [{int(r['partner_code'])}]  '{r['nome_erp']}'  →  '{r['nome_pipedrive']}'")

# ── 3. Amostra dos que NÃO serão corrigidos ───────────────────────────────────
print()
print("  Amostra — sem Pipedrive (ficará como está):")
sql_sem = f"""
SELECT d.partner_code, d.partner_name
FROM `{PROJ}.dm_partners.dim_partner` d
LEFT JOIN `{PROJ}.silver_comercial.param_com_entity_bridge` e
  ON e.partner_code = d.partner_code
WHERE d.partner_name LIKE '%?%'
  AND (e.org_name IS NULL OR e.org_name LIKE '%?%')
ORDER BY d.partner_name
LIMIT 15
"""
for _, r in client.query(sql_sem).to_dataframe().iterrows():
    print(f"  [{int(r['partner_code'])}]  '{r['partner_name']}'")

print()
print("Confirme para aplicar o UPDATE. Ctrl+C para cancelar.")
input(">>> Pressione ENTER para continuar...")

# ── 4. UPDATE dim_partner via Pipedrive ───────────────────────────────────────
print()
print("[1/3] Atualizando dm_partners.dim_partner com nomes do Pipedrive...")
sql_upd = f"""
UPDATE `{PROJ}.dm_partners.dim_partner` d
SET
  partner_name = e.org_name,
  legal_name   = CASE
    WHEN d.legal_name LIKE '%?%' THEN e.org_name
    ELSE d.legal_name
  END
FROM `{PROJ}.silver_comercial.param_com_entity_bridge` e
WHERE e.partner_code = d.partner_code
  AND d.partner_name LIKE '%?%'
  AND e.org_name IS NOT NULL
  AND e.org_name NOT LIKE '%?%'
"""
job = client.query(sql_upd)
job.result()
print(f"  ✅ UPDATE executado")

# Verificar resultado
r2 = client.query(f"""
  SELECT
    COUNTIF(partner_name LIKE '%?%') AS ainda_corrompidos,
    COUNT(*) AS total
  FROM `{PROJ}.dm_partners.dim_partner`
""").to_dataframe().iloc[0]
print(f"  dim_partner após UPDATE: {int(r2['ainda_corrompidos'])} corrompidos / {int(r2['total'])} total")

# ── 5. Corrigir param_com_entity_bridge.partner_name ──────────────────────────
print()
print("[2/3] Atualizando param_com_entity_bridge.partner_name com org_name...")
sql_bridge = f"""
UPDATE `{PROJ}.silver_comercial.param_com_entity_bridge`
SET partner_name = org_name
WHERE partner_name LIKE '%?%'
  AND org_name IS NOT NULL
  AND org_name NOT LIKE '%?%'
"""
job2 = client.query(sql_bridge)
job2.result()

r3 = client.query(f"""
  SELECT COUNTIF(partner_name LIKE '%?%') AS ainda_corrompidos, COUNT(*) AS total
  FROM `{PROJ}.silver_comercial.param_com_entity_bridge`
""").to_dataframe().iloc[0]
print(f"  ✅ entity_bridge após UPDATE: {int(r3['ainda_corrompidos'])} corrompidos / {int(r3['total'])} total")

# ── 6. Verificar gold_com_cliente_360 (usa partner_name) ─────────────────────
print()
print("[3/3] Verificando cobertura final em gold_com_cliente_360...")
r4 = client.query(f"""
  SELECT
    COUNTIF(partner_name LIKE '%?%') AS corrompidos,
    COUNT(*) AS total
  FROM `{PROJ}.gold_comercial.gold_com_cliente_360`
""").to_dataframe().iloc[0]
print(f"  gold_com_cliente_360: {int(r4['corrompidos'])} corrompidos / {int(r4['total'])} total")
print()

# ── Resumo final ──────────────────────────────────────────────────────────────
print("=" * 72)
print("  PRÓXIMOS PASSOS")
print("=" * 72)
print("  1. Rebuildar gold_comercial para propagar os nomes corrigidos:")
print("     py -3 sql/gold_comercial/run_gold_comercial.py")
print("  2. Rebuildar silver_comercial para propagar (param_com_entity_bridge atualizado):")
print("     py -3 sql/silver_comercial/run_silver_comercial.py")
print("  3. Para os sem Pipedrive: manter tabela param_encoding_manual_corrections")
print("=" * 72)
