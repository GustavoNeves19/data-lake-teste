"""
Popula param_com_entity_bridge: ERP partner_code ↔ Pipedrive org_id.

Estratégia de match (em ordem de confiança):
  1. CNPJ normalizado (dígitos apenas) — match exato, score 100
  2. Nome do cliente fuzzy (WRatio >= 85) — score = fuzzy score
  3. Registros sem match ficam com org_id=NULL e match_type='unmatched'

Linkage GoTo NÃO entra nesta tabela pelo cliente — sem cobertura de telefone.
Ligações GoTo são linkadas pelo vendedor (goto_users → crm_user → deals.owner_id).

Executar: py -3 sql/silver_comercial/populate_entity_bridge.py

Pré-requisito: pip install pandas rapidfuzz google-cloud-bigquery
"""
import io, os, re, sys
from datetime import timezone, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import pandas as pd
from rapidfuzz import process, fuzz
from google.cloud import bigquery

# ── Config ────────────────────────────────────────────────────────────────────
BQ_PROJECT  = "sapient-metrics-492914-m7"
DATASET_ID  = "silver_comercial"
LOCATION    = "us-east1"
CREDS_BQ    = r"C:\teste\sapient-metrics.json"

FUZZY_THRESHOLD  = 88  # score mínimo para aceitar match por nome
FUZZY_MIN_LEN    = 15  # nome mínimo (chars) para tentar fuzzy — evita "ANDRE" → "ANDRESA..."

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDS_BQ
client = bigquery.Client(project=BQ_PROJECT, location=LOCATION)


# ── Helpers ───────────────────────────────────────────────────────────────────

def norm_cnpj(raw: str) -> str:
    """Remove tudo que não for dígito. Retorna '' se vazio/None."""
    if not raw:
        return ""
    return re.sub(r"\D", "", str(raw))


def norm_name(name: str) -> str:
    """Upper + strip para comparação de nomes."""
    if not name:
        return ""
    return str(name).upper().strip()


# ── Carregar ERP ──────────────────────────────────────────────────────────────

def load_erp_clients() -> pd.DataFrame:
    """
    Clientes ERP priorizando:
      1. Carteira ativa (param_com_rfv_carteira) — os mais relevantes para o Comercial
      2. Todos com pedido faturado nos últimos 24 meses — clientes ativos

    Nome: COALESCE(dim_partner.partner_name, carteira.partner_name)
      — dim_partner cobre <1% da carteira, então o nome da carteira (planilha Alves)
        é o principal vetor de fuzzy match para os 1.500+ clientes da carteira.

    CNPJ vem do dim_partner (14 dígitos = CNPJ empresa; ignoramos CPF de 11 dígitos).
    """
    print("  Carregando clientes ERP (carteira + ativos 24m)...")
    df = client.query("""
        WITH carteira AS (
            SELECT DISTINCT partner_code, partner_name AS cart_name FROM
            `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
            WHERE is_active = TRUE
        ),
        ativos AS (
            SELECT DISTINCT partner_code FROM
            `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
            WHERE order_status IN (3, 4)
              AND order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 24 MONTH)
              AND partner_code NOT IN (SELECT partner_code FROM carteira)
        ),
        universo AS (
            SELECT partner_code, cart_name FROM carteira
            UNION ALL
            SELECT partner_code, NULL  FROM ativos
        )
        SELECT
            u.partner_code,
            COALESCE(p.partner_name, u.cart_name) AS partner_name,
            CASE
                WHEN LENGTH(REGEXP_REPLACE(p.tax_id, r'[^0-9]', '')) = 14
                THEN REGEXP_REPLACE(p.tax_id, r'[^0-9]', '')
                ELSE NULL
            END AS tax_id   -- só CNPJ (14 dígitos), ignora CPF
        FROM universo u
        LEFT JOIN `sapient-metrics-492914-m7.dm_partners.dim_partner` p
            ON p.partner_code = u.partner_code
    """).to_dataframe()
    df["tax_id_norm"] = df["tax_id"].apply(norm_cnpj)
    df["name_norm"]   = df["partner_name"].apply(norm_name)
    in_carteira = df["partner_code"].isin(
        client.query("""
            SELECT DISTINCT CAST(partner_code AS INT64) AS partner_code
            FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
            WHERE is_active = TRUE
        """).to_dataframe()["partner_code"]
    ).sum()
    print(f"    {len(df):,} clientes ERP ({in_carteira:,} da carteira RFV ativa)")
    with_name = (df["name_norm"] != "").sum()
    with_cnpj = (df["tax_id_norm"] != "").sum()
    print(f"    {with_name:,} com nome | {with_cnpj:,} com CNPJ")
    return df


# ── Carregar Pipedrive orgs ───────────────────────────────────────────────────

def load_crm_orgs() -> pd.DataFrame:
    """
    dim_crm_organization + CNPJ inferido dos deals (cf_cnpj__cpf).
    Para cada org_id pega o CNPJ mais frequente nos seus deals.
    """
    print("  Carregando orgs Pipedrive + CNPJ dos deals...")

    # Todos os deals com CNPJ preenchido, de qualquer pipeline
    deals = client.query("""
        SELECT org_id, cf_cnpj__cpf AS cnpj_raw
        FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_farmacia`
        WHERE org_id IS NOT NULL AND cf_cnpj__cpf IS NOT NULL AND cf_cnpj__cpf != ''
        UNION ALL
        SELECT org_id, cf_cnpj__cpf
        FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_distribuidores`
        WHERE org_id IS NOT NULL AND cf_cnpj__cpf IS NOT NULL AND cf_cnpj__cpf != ''
        UNION ALL
        SELECT org_id, cf_cnpj__cpf
        FROM `sapient-metrics-492914-m7.crm_raw.funil_vendas_farmacia`
        WHERE org_id IS NOT NULL AND cf_cnpj__cpf IS NOT NULL AND cf_cnpj__cpf != ''
    """).to_dataframe()
    deals["cnpj_norm"] = deals["cnpj_raw"].apply(norm_cnpj)
    deals = deals[deals["cnpj_norm"].str.len() >= 11]  # mínimo CPF válido

    # Para cada org_id: CNPJ mais frequente
    cnpj_by_org = (
        deals.groupby(["org_id", "cnpj_norm"])
        .size()
        .reset_index(name="cnt")
        .sort_values("cnt", ascending=False)
        .drop_duplicates(subset="org_id")
        .set_index("org_id")["cnpj_norm"]
        .to_dict()
    )

    # Todas as orgs
    orgs = client.query("""
        SELECT org_id, name AS org_name, is_active
        FROM `sapient-metrics-492914-m7.crm_raw.dim_crm_organization`
    """).to_dataframe()
    orgs["cnpj_norm"] = orgs["org_id"].map(cnpj_by_org).fillna("")
    orgs["name_norm"] = orgs["org_name"].apply(norm_name)

    with_cnpj = (orgs["cnpj_norm"] != "").sum()
    print(f"    {len(orgs):,} orgs Pipedrive | {with_cnpj:,} com CNPJ ({with_cnpj*100//len(orgs)}%)")
    return orgs


# ── Match ─────────────────────────────────────────────────────────────────────

def build_bridge(erp: pd.DataFrame, crm: pd.DataFrame) -> pd.DataFrame:
    # Índice CRM: cnpj_norm → lista de org_ids
    cnpj_to_orgs: dict[str, list] = {}
    for _, row in crm[crm["cnpj_norm"] != ""].iterrows():
        k = row["cnpj_norm"]
        cnpj_to_orgs.setdefault(k, [])
        cnpj_to_orgs[k].append(row)

    # Índice CRM: name_norm → lista de org rows
    # Filtra nomes muito curtos para evitar falsos positivos
    # ("MEDICAMENTOS LTDA" matchando qualquer empresa do setor)
    crm_fuzzy = crm[crm["name_norm"].str.len() >= FUZZY_MIN_LEN]
    crm_names = crm_fuzzy["name_norm"].tolist()
    crm_name_map: dict[str, pd.Series] = {
        row["name_norm"]: row for _, row in crm_fuzzy.iterrows()
    }

    rows = []
    now  = datetime.now(tz=timezone.utc)

    for _, erp_row in erp.iterrows():
        pcode = int(erp_row["partner_code"])
        pname = erp_row.get("partner_name") or ""
        taxid = erp_row.get("tax_id_norm", "") or ""

        matched = False

        # ── 1. CNPJ exact ────────────────────────────────────────────────────
        if taxid and len(taxid) >= 11 and taxid in cnpj_to_orgs:
            for org_row in cnpj_to_orgs[taxid]:
                rows.append({
                    "partner_code": pcode,
                    "partner_name": pname,
                    "tax_id":       taxid,
                    "org_id":       int(org_row["org_id"]),
                    "org_name":     org_row["org_name"],
                    "match_type":   "cnpj_exact",
                    "match_score":  100.0,
                    "is_active":    True,
                    "created_at":   now,
                    "updated_at":   now,
                })
            matched = True

        # ── 2. Fuzzy name ─────────────────────────────────────────────────────
        if not matched and erp_row["name_norm"] and len(erp_row["name_norm"]) >= FUZZY_MIN_LEN:
            m = process.extractOne(
                erp_row["name_norm"], crm_names, scorer=fuzz.WRatio
            )
            if m and m[1] >= FUZZY_THRESHOLD:
                org_row = crm_name_map[m[0]]
                rows.append({
                    "partner_code": pcode,
                    "partner_name": pname,
                    "tax_id":       taxid,
                    "org_id":       int(org_row["org_id"]),
                    "org_name":     org_row["org_name"],
                    "match_type":   "name_fuzzy",
                    "match_score":  float(m[1]),
                    "is_active":    True,
                    "created_at":   now,
                    "updated_at":   now,
                })
                matched = True

        # ── 3. Unmatched ──────────────────────────────────────────────────────
        if not matched:
            rows.append({
                "partner_code": pcode,
                "partner_name": pname,
                "tax_id":       taxid,
                "org_id":       None,
                "org_name":     None,
                "match_type":   "unmatched",
                "match_score":  0.0,
                "is_active":    False,
                "created_at":   now,
                "updated_at":   now,
            })

    return pd.DataFrame(rows)


# ── Inserir no BQ ─────────────────────────────────────────────────────────────

def upsert_bridge(bridge: pd.DataFrame) -> None:
    """WRITE_TRUNCATE — recria a tabela a cada execução."""
    table_ref = f"{BQ_PROJECT}.{DATASET_ID}.param_com_entity_bridge"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("partner_code",  "INT64",   mode="REQUIRED"),
            bigquery.SchemaField("partner_name",  "STRING"),
            bigquery.SchemaField("tax_id",        "STRING"),
            bigquery.SchemaField("org_id",        "INT64"),
            bigquery.SchemaField("org_name",      "STRING"),
            bigquery.SchemaField("match_type",    "STRING"),
            bigquery.SchemaField("match_score",   "FLOAT64"),
            bigquery.SchemaField("is_active",     "BOOL"),
            bigquery.SchemaField("created_at",    "TIMESTAMP"),
            bigquery.SchemaField("updated_at",    "TIMESTAMP"),
        ],
    )
    job = client.load_table_from_dataframe(bridge, table_ref, job_config=job_config)
    job.result()
    tbl = client.get_table(table_ref)
    print(f"    Tabela atualizada: {tbl.num_rows:,} linhas ({tbl.num_bytes/1024/1024:.2f} MB)")


# ── Relatório ──────────────────────────────────────────────────────────────────

def report(bridge: pd.DataFrame) -> None:
    total = len(bridge)
    by_type = bridge.groupby("match_type").agg(
        qtd=("partner_code", "count"),
        pct=("partner_code", lambda x: round(len(x) * 100 / total, 1))
    ).reset_index()

    print()
    print("  RESULTADO DO MATCH:")
    print(f"  {'Tipo':<15} {'Qtd':>7} {'%':>6}")
    print(f"  {'-'*30}")
    for _, r in by_type.sort_values("qtd", ascending=False).iterrows():
        print(f"  {r['match_type']:<15} {r['qtd']:>7,} {r['pct']:>5.1f}%")
    print(f"  {'TOTAL':<15} {total:>7,}")

    matched = bridge[bridge["match_type"] != "unmatched"]
    print(f"\n  Clientes ERP linkados ao Pipedrive: {matched['partner_code'].nunique():,} "
          f"({matched['partner_code'].nunique()*100//total}%)")
    print(f"  Orgs Pipedrive mapeadas:            {matched['org_id'].nunique():,}")

    # Fuzzy borderline (score 85-92) para revisão
    borderline = bridge[
        (bridge["match_type"] == "name_fuzzy") &
        (bridge["match_score"] < 92)
    ].sort_values("match_score", ascending=False)
    if len(borderline) > 0:
        print(f"\n  FUZZY BORDERLINE (score 85-91) — revisar manualmente: {len(borderline)}")
        for _, r in borderline.head(20).iterrows():
            print(f"    {r['match_score']:.0f} | '{r['partner_name']}' => '{r['org_name']}'")
        # Salvar para revisão
        out = Path(__file__).parent / "bridge_borderline.csv"
        borderline.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"    Salvo em: {out}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 72)
    print("populate_entity_bridge — ERP partner_code ↔ Pipedrive org_id")
    print("=" * 72)

    print("\n[1/4] Carregando ERP...")
    erp = load_erp_clients()

    print("\n[2/4] Carregando Pipedrive...")
    crm = load_crm_orgs()

    print(f"\n[3/4] Executando match (threshold fuzzy={FUZZY_THRESHOLD})...")
    bridge = build_bridge(erp, crm)
    report(bridge)

    print("\n[4/4] Gravando param_com_entity_bridge no BQ...")
    upsert_bridge(bridge)

    print()
    print("=" * 72)
    print("PRÓXIMOS PASSOS:")
    print("  1. Revisar bridge_borderline.csv — validar fuzzy matches duvidosos")
    print("  2. Inserir manualmente via BQ Console os não-matchados relevantes")
    print("  3. Usar a bridge no Gold: JOIN por partner_code → org_id")
    print("  4. GoTo linkage: goto_extensions.user_id → crm_raw.dim_crm_user")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
