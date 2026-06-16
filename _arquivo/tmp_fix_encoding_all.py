"""
Corrige encoding corrompido ('?') em todas as tabelas BQ afetadas.

Estratégia:
  Tier 1 — Tabelas de dimensão (fonte): lê → aplica dicionário → TRUNCATE + re-insert
  Tier 2 — fact_sales_order.salesperson_name: UPDATE direto nos registros corrompidos
  Tier 3 — Tabelas silver/gold derivadas: serão corrigidas no próximo rebuild

O dicionário vem de transform/mappings/ (common + companies + products).
Palavras não cobertas pelo dicionário ficam marcadas no relatório final.
"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni')

import re
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from transform.mappings import DOMAIN_ENCODING_PATTERNS

PROJ     = "sapient-metrics-492914-m7"
CREDS_BQ = r"C:\teste\sapient-metrics.json"

creds = service_account.Credentials.from_service_account_file(
    CREDS_BQ, scopes=["https://www.googleapis.com/auth/cloud-platform"])
client = bigquery.Client(credentials=creds, project=PROJ)

# ── Dicionário de correções ────────────────────────────────────────────────────
# Ordena por tamanho decrescente para evitar substituição parcial
FIXES = dict(sorted(DOMAIN_ENCODING_PATTERNS.items(), key=lambda x: -len(x[0])))

def apply_fixes(text: str) -> str:
    """Aplica todos os padrões do dicionário em sequência."""
    if not isinstance(text, str) or '?' not in text:
        return text
    for wrong, right in FIXES.items():
        if wrong in text:
            text = text.replace(wrong, right)
    return text

def apply_fixes_series(series: pd.Series) -> pd.Series:
    """Aplica correções a uma Series string."""
    return series.apply(apply_fixes)

def count_remaining_q(series: pd.Series) -> int:
    return int(series.str.contains('?', na=False, regex=False).sum())

# ── Tabelas Tier 1 — dimensões para TRUNCATE + re-insert ──────────────────────
DIM_TABLES = [
    # (dataset, table, columns_to_fix)
    ("dm_partners",  "dim_partner",         ["partner_name", "legal_name"]),
    ("dm_partners",  "dim_salesperson",      ["salesperson_name"]),
    ("dm_partners",  "dim_salesperson_group",["group_name"]),
    ("dm_partners",  "dim_carrier",          ["carrier_name"]),
    ("dm_products",  "dim_item",             ["item_name"]),
    ("dm_products",  "dim_material",         ["material_name"]),
    ("dm_products",  "dim_family",           ["family_name"]),
    ("dm_orders",    "dim_operation_nature", ["nature_name"]),
    ("dm_orders",    "dim_payment_condition",["payment_cond_name"]),
    ("dm_payments",  "dim_financial_item",   ["financial_item_name"]),
    ("dm_payments",  "dim_bank",             ["bank_name"]),
    ("dm_payments",  "dim_department",       ["department_name"]),
    # silver param table
    ("silver_comercial", "param_com_entity_bridge", ["partner_name"]),
    # silver financeiro param
    ("silver_financeiro", "param_fin_plano_contas", ["financial_item_name"]),
]


def fix_dim_table(dataset: str, table: str, cols: list) -> dict:
    """Lê toda a tabela, aplica dicionário nas colunas especificadas, recarrega."""
    table_id = f"{PROJ}.{dataset}.{table}"

    df = client.query(f"SELECT * FROM `{table_id}`").to_dataframe()
    if df.empty:
        return {"table": f"{dataset}.{table}", "status": "empty", "fixed": 0, "remaining": 0}

    total_before = sum(int(df[c].str.contains('?', na=False, regex=False).sum())
                       for c in cols if c in df.columns)
    if total_before == 0:
        return {"table": f"{dataset}.{table}", "status": "already_clean", "fixed": 0, "remaining": 0}

    df_fixed = df.copy()
    for col in cols:
        if col in df_fixed.columns:
            df_fixed[col] = apply_fixes_series(df_fixed[col])

    total_after  = sum(count_remaining_q(df_fixed[c]) for c in cols if c in df_fixed.columns)
    total_fixed  = total_before - total_after

    # TRUNCATE + re-insert via load_table_from_dataframe
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(df_fixed, table_id, job_config=job_config)
    job.result()
    if job.errors:
        return {"table": f"{dataset}.{table}", "status": "error", "fixed": total_fixed,
                "remaining": total_after, "error": str(job.errors[:1])}

    # Amostras que ainda têm '?' (para relatório)
    unfixed_samples = []
    for col in cols:
        if col in df_fixed.columns:
            mask = df_fixed[col].str.contains('?', na=False, regex=False)
            unfixed_samples.extend(df_fixed.loc[mask, col].unique()[:5].tolist())

    return {
        "table": f"{dataset}.{table}", "status": "fixed",
        "fixed": total_fixed, "remaining": total_after,
        "unfixed_samples": unfixed_samples[:8],
    }


def fix_fact_salesperson():
    """
    Corrige salesperson_name em fact_sales_order via UPDATE (só os registros corrompidos).
    BigQuery UPDATE: monta CASE WHEN para cada valor único corrompido.
    """
    table_id = f"{PROJ}.dm_orders.fact_sales_order"

    # Lê valores únicos corrompidos
    df_bad = client.query(f"""
        SELECT DISTINCT salesperson_name
        FROM `{table_id}`
        WHERE salesperson_name LIKE '%?%'
    """).to_dataframe()

    if df_bad.empty:
        return {"table": "dm_orders.fact_sales_order.salesperson_name",
                "status": "already_clean", "fixed": 0}

    # Aplica dicionário
    corrections = {}
    for val in df_bad['salesperson_name']:
        fixed = apply_fixes(val)
        if fixed != val:
            corrections[val] = fixed

    if not corrections:
        return {"table": "dm_orders.fact_sales_order.salesperson_name",
                "status": "no_dict_match", "fixed": 0,
                "samples": df_bad['salesperson_name'].tolist()[:5]}

    # UPDATE via CASE WHEN
    when_clauses = "\n      ".join(
        f"WHEN salesperson_name = '{v.replace(chr(39), chr(39)+chr(39))}' THEN '{c.replace(chr(39), chr(39)+chr(39))}'"
        for v, c in corrections.items()
    )
    sql = f"""
    UPDATE `{table_id}`
    SET salesperson_name = CASE
      {when_clauses}
      ELSE salesperson_name
    END
    WHERE salesperson_name LIKE '%?%'
    """
    job = client.query(sql)
    job.result()

    return {
        "table": "dm_orders.fact_sales_order.salesperson_name",
        "status": "fixed",
        "fixed": len(corrections),
        "corrections": corrections,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
print("=" * 72)
print("  FIX ENCODING — Correção global de nomes corrompidos no BQ")
print(f"  Padrões no dicionário: {len(FIXES)}")
print("=" * 72)

results = []

print("\n[TIER 1] Tabelas de dimensão — TRUNCATE + re-insert com nomes corrigidos")
print(f"{'─'*72}")
for ds, tbl, cols in DIM_TABLES:
    print(f"  {ds}.{tbl} ...", end=" ", flush=True)
    r = fix_dim_table(ds, tbl, cols)
    results.append(r)
    if r['status'] == 'already_clean':
        print("✅ já limpa")
    elif r['status'] == 'empty':
        print("⬜ vazia")
    elif r['status'] == 'error':
        print(f"❌ ERRO: {r.get('error','')}")
    else:
        remaining = r.get('remaining', 0)
        print(f"✅ {r['fixed']} corrigidos | {remaining} restantes", end="")
        if remaining > 0 and r.get('unfixed_samples'):
            print(f"  ← {r['unfixed_samples'][:3]}", end="")
        print()

print(f"\n[TIER 2] fact_sales_order.salesperson_name — UPDATE direto")
print(f"{'─'*72}")
r2 = fix_fact_salesperson()
results.append(r2)
status = r2['status']
if status == 'already_clean':
    print("  ✅ já limpa")
elif status == 'no_dict_match':
    print(f"  ⚠️  sem match no dicionário. Amostras: {r2.get('samples', [])}")
else:
    print(f"  ✅ {r2['fixed']} valores corrigidos")
    for old, new in list(r2.get('corrections', {}).items())[:5]:
        print(f"    '{old}' → '{new}'")

# ── Relatório final ────────────────────────────────────────────────────────────
print(f"\n{'='*72}")
print("  RELATÓRIO FINAL")
print(f"{'='*72}")
total_fixed = sum(r.get('fixed', 0) for r in results)
total_remaining = sum(r.get('remaining', 0) for r in results)
print(f"  Total corrigido:  {total_fixed}")
print(f"  Total restante:   {total_remaining}  (não cobertos pelo dicionário)")

if total_remaining > 0:
    print("\n  Valores ainda corrompidos (nomes próprios / fora do dicionário):")
    for r in results:
        if r.get('remaining', 0) > 0 and r.get('unfixed_samples'):
            print(f"    {r['table']}: {r['unfixed_samples'][:5]}")

print(f"\n[TIER 3] Próximo passo: rebuildar silver/gold para propagar correções")
print("  py -3 sql/silver_comercial/run_silver_comercial.py")
print("  py -3 sql/gold_comercial/run_gold_comercial.py")
print("  (silver_financeiro será corrigido no próximo ETL completo)")
print("=" * 72)
