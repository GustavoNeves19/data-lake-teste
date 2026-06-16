"""
Atualiza crm_raw.dim_crm_user com dados frescos do Pipedrive
e sincroniza param_com_vendedor_map com os vendedores ativos.

Execução: py -3 tmp_update_crm_users.py
"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

# ── Configuração ──────────────────────────────────────────
PROJ        = "sapient-metrics-492914-m7"
CREDS_BQ    = r"C:\teste\sapient-metrics.json"
API_TOKEN   = os.environ["PIPEDRIVE_API_TOKEN"]
BASE_URL    = os.environ["PIPEDRIVE_BASE_URL"].replace("/api/v2", "/api/v1")

# Mapa manual: rfv_salesperson → palavras-chave para encontrar o user no Pipedrive
# Ordem: sobrenome ou nome curto usado na RFV → substring no nome completo do CRM
VENDEDOR_MAP_RULES = [
    # (rfv_salesperson, substring_no_nome_crm)
    ("Guilherme",  "Guilherme"),
    ("Ribeiro",    "Ribeiro"),
    ("Kaua",       "Kauã Rodrigues"),   # Kauã Rodrigues (não Kauã Sequim)
    ("Richard",    "Richard"),
    ("Giovanna",   "Geovana"),           # Geovana gomes → Giovanna no ERP
    ("Eduardo",    "Eduardo"),
    # Ramos será adicionado depois de identificar pelo nome
]

creds = service_account.Credentials.from_service_account_file(
    CREDS_BQ, scopes=["https://www.googleapis.com/auth/cloud-platform"])
client = bigquery.Client(credentials=creds, project=PROJ)

# ── 1. Pull de usuários do Pipedrive ─────────────────────
print("=" * 68)
print("  PUXANDO USUÁRIOS DO PIPEDRIVE API v1")
print("=" * 68)

headers = {"x-api-token": API_TOKEN}
resp = requests.get(
    f"{BASE_URL}/users",
    headers=headers,
    params={"limit": 200},
    timeout=30,
)
resp.raise_for_status()
data = resp.json()

users_raw = data.get("data", []) or []
print(f"  {len(users_raw)} usuários retornados pelo Pipedrive")
print()

rows_user = []
for u in users_raw:
    rows_user.append({
        "user_id":       int(u["id"]),
        "name":          u.get("name", ""),
        "email":         u.get("email", ""),
        "is_active":     bool(u.get("active_flag", True)),
        "etl_loaded_at": datetime.now(timezone.utc),
    })
    print(f"  {u['id']:>10}  {u.get('name',''):30s}  {u.get('email','')}")

print()

# ── 2. Atualiza dim_crm_user ─────────────────────────────
print("  Atualizando crm_raw.dim_crm_user (TRUNCATE + load)...")
df_users = pd.DataFrame(rows_user)
df_users["user_id"] = df_users["user_id"].astype("Int64")

table_ref = f"{PROJ}.crm_raw.dim_crm_user"
job_config = bigquery.LoadJobConfig(
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    schema=[
        bigquery.SchemaField("user_id",       "INTEGER"),
        bigquery.SchemaField("name",           "STRING"),
        bigquery.SchemaField("email",          "STRING"),
        bigquery.SchemaField("is_active",      "BOOLEAN"),
        bigquery.SchemaField("etl_loaded_at",  "TIMESTAMP"),
    ],
)
job = client.load_table_from_dataframe(df_users, table_ref, job_config=job_config)
job.result()
print(f"  ✓ dim_crm_user atualizada: {len(df_users)} usuários\n")

# ── 3. Monta param_com_vendedor_map atualizado ───────────
print("=" * 68)
print("  ATUALIZANDO param_com_vendedor_map")
print("=" * 68)

# Lê usuários ativos do BQ (recém-carregados)
df_crm = pd.DataFrame(rows_user)
df_crm = df_crm[df_crm["is_active"] == True]

new_map = []
for rfv_name, search_str in VENDEDOR_MAP_RULES:
    match = df_crm[df_crm["name"].str.contains(search_str, case=False, na=False)]
    if match.empty:
        print(f"  ⚠ NÃO ENCONTRADO: '{rfv_name}' (buscando '{search_str}')")
        continue
    row = match.iloc[0]
    new_map.append({
        "rfv_salesperson": rfv_name,
        "crm_user_id":     int(row["user_id"]),
        "crm_user_name":   row["name"],
    })
    print(f"  ✓  rfv='{rfv_name}' → CRM id={int(row['user_id'])} nome='{row['name']}'")

# Procurar Ramos automaticamente (não estava na lista manual, busca por Ramos)
ramos_match = df_crm[
    df_crm["name"].str.contains("Ramos", case=False, na=False) &
    ~df_crm["name"].isin([r["crm_user_name"] for r in new_map])
]
if not ramos_match.empty:
    r = ramos_match.iloc[0]
    new_map.append({
        "rfv_salesperson": "Ramos",
        "crm_user_id":     int(r["user_id"]),
        "crm_user_name":   r["name"],
    })
    print(f"  ✓  rfv='Ramos' → CRM id={int(r['user_id'])} nome='{r['name']}'")
else:
    print("  ⚠ Ramos não encontrado no Pipedrive ainda (pode ainda não ter sido cadastrado)")

print()
print(f"  Total: {len(new_map)} vendedores mapeados")

if new_map:
    df_map = pd.DataFrame(new_map)
    df_map["crm_user_id"] = df_map["crm_user_id"].astype("Int64")
    print()
    print("  Preview do novo mapa:")
    print(df_map.to_string(index=False))

    confirm = input("\n  Salvar param_com_vendedor_map no BQ? (s/n): ").strip().lower()
    if confirm == "s":
        map_ref = f"{PROJ}.silver_comercial.param_com_vendedor_map"
        job_config2 = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=[
                bigquery.SchemaField("rfv_salesperson", "STRING"),
                bigquery.SchemaField("crm_user_id",     "INTEGER"),
                bigquery.SchemaField("crm_user_name",   "STRING"),
            ],
        )
        job2 = client.load_table_from_dataframe(df_map, map_ref, job_config=job_config2)
        job2.result()
        print(f"  ✓ param_com_vendedor_map salvo: {len(df_map)} linhas")
    else:
        print("  Cancelado. dim_crm_user já foi atualizada.")

print()
print("=" * 68)
print("  DONE")
print("=" * 68)
