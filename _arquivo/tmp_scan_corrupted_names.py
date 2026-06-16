"""
Escaneia todos os datasets do projeto BQ em busca de colunas
com nomes de parceiros/clientes corrompidos (contendo '?').
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform'])
client = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

PROJ = 'sapient-metrics-492914-m7'

# 1. Listar todos os datasets
datasets = list(client.list_datasets(project=PROJ))
print(f"Datasets encontrados: {[d.dataset_id for d in datasets]}\n")

# 2. Para cada dataset, listar tabelas e checar colunas de nome
name_cols = ['partner_name', 'client_name', 'customer_name', 'nome', 'name',
             'company_name', 'org_name', 'person_name', 'display_name']

print("=" * 70)
print("Tabelas com colunas de nome de parceiro/cliente")
print("=" * 70)

candidates = []

for ds in datasets:
    tables = list(client.list_tables(f"{PROJ}.{ds.dataset_id}"))
    for tbl in tables:
        ref = client.get_table(f"{PROJ}.{ds.dataset_id}.{tbl.table_id}")
        for field in ref.schema:
            if field.field_type in ('STRING',) and any(nc in field.name.lower() for nc in name_cols):
                candidates.append({
                    'dataset': ds.dataset_id,
                    'table': tbl.table_id,
                    'column': field.name,
                    'full': f"{PROJ}.{ds.dataset_id}.{tbl.table_id}",
                })

for c in candidates:
    print(f"  {c['dataset']}.{c['table']}.{c['column']}")

print(f"\nTotal de colunas candidatas: {len(candidates)}")

# 3. Para cada candidata, contar quantos '?' existem
print("\n" + "=" * 70)
print("Contagem de registros corrompidos por coluna")
print("=" * 70)

corrupted_found = []
for c in candidates:
    try:
        sql = f"""
        SELECT COUNT(*) AS total,
               COUNTIF({c['column']} LIKE '%?%') AS corrompidos
        FROM `{c['full']}`
        """
        row = client.query(sql).to_dataframe().iloc[0]
        total = int(row['total'])
        corr  = int(row['corrompidos'])
        if corr > 0:
            pct = round(corr / total * 100, 1) if total > 0 else 0
            print(f"  ⚠️  {c['dataset']}.{c['table']}.{c['column']}: {corr}/{total} ({pct}%) corrompidos")
            corrupted_found.append({**c, 'total': total, 'corrompidos': corr})
        else:
            print(f"  ✅  {c['dataset']}.{c['table']}.{c['column']}: OK ({total} registros)")
    except Exception as e:
        print(f"  ❌  {c['dataset']}.{c['table']}.{c['column']}: erro — {str(e)[:80]}")

print(f"\nTabelas com corrupção: {len(corrupted_found)}")
for c in corrupted_found:
    print(f"  → {c['dataset']}.{c['table']}.{c['column']}: {c['corrompidos']}/{c['total']}")
