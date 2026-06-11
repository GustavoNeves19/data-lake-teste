"""
Popula param_com_rfv_carteira a partir das planilhas RFV do Alves.

Lógica (v2 — base completa):
  1. Lê a aba GERAL de cada planilha → todos os clientes da família
  2. Lê as abas por VENDEDOR → mapa de atribuição (cliente → vendedor)
  3. Para clientes no geral sem vendedor atribuído → rfv_salesperson = "Sem Vendedor"
  4. Match exato + fuzzy contra ERP (SQL Server)
  5. TRUNCATE + INSERT em param_com_rfv_carteira (produção)

Executar: py -3 sql/silver_comercial/populate_carteira.py

Pré-requisito: pip install pandas openpyxl rapidfuzz google-cloud-bigquery pyodbc python-dotenv
"""
import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import pandas as pd
from rapidfuzz import process, fuzz
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import pyodbc

# ── Config ────────────────────────────────────────────────────────────────────
_dir = Path(__file__).resolve()
for _ in range(8):
    _dir = _dir.parent
    if (_dir / ".env").exists():
        load_dotenv(_dir / ".env")
        break

BQ_PROJECT = "sapient-metrics-492914-m7"
DATASET_ID = "silver_comercial"
LOCATION   = "us-east1"
CREDS_BQ   = r"C:\teste\sapient-metrics.json"

HOSP_FILE = r"C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026 (1).xlsx"
FARM_FILE = r"C:\Users\gusta\Downloads\RFV Farmácias 01-04-2025 até 30-04-2026 (1).xlsx"
SAC_FILE  = r"C:\Users\gusta\Downloads\RFV SAC 01-04-2025 até 30-04-2026 (1).xlsx"

FUZZY_THRESHOLD = 88  # score mínimo para match automático (0-100)

# ── Mapeamento de abas ────────────────────────────────────────────────────────
# Aba geral = todos os clientes da família (fonte primária de clientes)
# Abas por vendedor = fonte de atribuição de salesperson
# Arquivos de referência: abril/2026 (enviados pelo Alves em mai/2026)

HOSP_GERAL_SHEET   = "Sem fórmula Geral"      # 786 únicos (abril/2026)
HOSP_VENDEDOR_SHEETS = {
    "Base inicial - vendedor A": "Guilherme",
    "Base inicial - Vendedor B": "Kaua",
    "Base inicial - Vendedor C": "Richard",
}

FARM_GERAL_SHEET   = "Sem Fórmula"            # 248 únicos (abril/2026 — Ribeiro revisou carteira)
FARM_VENDEDOR_SHEETS = {
    "Sem Fórmula": "Ribeiro",                  # FARMACIAS tem só 1 vendedor
}

SAC_GERAL_SHEET    = "Sem Fórmula"            # 79 únicos (abril/2026)
SAC_VENDEDOR_SHEETS = {}                       # SAC sem separação por vendedor → "Sem Vendedor"


# ── ERP connection ────────────────────────────────────────────────────────────

def erp_conn():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.getenv('SQL_SERVER_HOST')},{os.getenv('SQL_SERVER_PORT')};"
        f"DATABASE={os.getenv('SQL_SERVER_DATABASE')};"
        f"UID={os.getenv('SQL_SERVER_USER')};"
        f"PWD={os.getenv('SQL_SERVER_PASSWORD')};"
    )
    return pyodbc.connect(conn_str, timeout=30)


# ── BQ client ────────────────────────────────────────────────────────────────

def bq_client():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_BQ,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=creds, project=BQ_PROJECT)


# ── Extração planilhas ────────────────────────────────────────────────────────

def extract_unique_clients(filepath: str, sheet_name: str) -> set:
    """Extrai nomes únicos de clientes de uma aba (coluna 0 = ID - CLIENTE)."""
    xls = pd.ExcelFile(filepath)
    if sheet_name not in xls.sheet_names:
        print(f"  [aviso] aba '{sheet_name}' não encontrada em {Path(filepath).name}")
        return set()
    df  = pd.read_excel(filepath, sheet_name=sheet_name)
    col = df.columns[0]
    clientes = df[col].dropna().astype(str).str.strip().unique()
    return {c for c in clientes if c and c.upper() not in ('ID - CLIENTE', 'NAN', '')}


def build_vendedor_map(filepath: str, vendedor_sheets: dict) -> dict:
    """
    Retorna dict: nome_cliente → salesperson_name
    Quando um cliente aparece em mais de um vendedor, mantém o primeiro encontrado.
    """
    mapping = {}
    xls = pd.ExcelFile(filepath)
    for sheet_name, vendedor in vendedor_sheets.items():
        if sheet_name not in xls.sheet_names:
            continue
        clientes = extract_unique_clients(filepath, sheet_name)
        for c in clientes:
            if c not in mapping:   # primeiro vendedor ganha
                mapping[c] = vendedor
    return mapping


def build_familia_df(familia: str, filepath: str,
                     geral_sheet: str, vendedor_sheets: dict) -> pd.DataFrame:
    """
    Monta DataFrame com (planilha_nome, rfv_familia, salesperson_name)
    para todos os clientes do geral, com vendedor quando disponível.
    """
    geral_clientes = extract_unique_clients(filepath, geral_sheet)
    print(f"  {familia} / Geral: {len(geral_clientes)} clientes únicos")

    vendedor_map = build_vendedor_map(filepath, vendedor_sheets)
    atribuidos = sum(1 for c in geral_clientes if c in vendedor_map)
    print(f"  {familia} / Com vendedor: {atribuidos} | Sem vendedor: {len(geral_clientes) - atribuidos}")

    rows = []
    for nome in sorted(geral_clientes):
        rows.append({
            "planilha_nome":    nome,
            "rfv_familia":      familia,
            "salesperson_name": vendedor_map.get(nome, "Sem Vendedor"),
        })
    return pd.DataFrame(rows)


# ── ERP partners ─────────────────────────────────────────────────────────────

def fetch_erp_partners(conn) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT YCODCLI, YNOMCLI FROM [CLIENTES OU FORNECEDORES] WHERE YTIPCLI = 'C'")
    data = [(int(r[0]), str(r[1]).strip()) for r in cur.fetchall() if r[0] is not None and r[1]]
    df = pd.DataFrame(data, columns=['partner_code', 'partner_name'])
    return df[df['partner_name'] != ''].copy()


# ── Fuzzy match ───────────────────────────────────────────────────────────────

def match_clients(planilha_df: pd.DataFrame, partners_df: pd.DataFrame) -> pd.DataFrame:
    partner_names = partners_df['partner_name'].tolist()
    name_to_codes = {}
    for _, r in partners_df.iterrows():
        name_to_codes.setdefault(r['partner_name'], []).append(r['partner_code'])

    results = []
    for _, row in planilha_df.iterrows():
        query = row['planilha_nome']
        if query in name_to_codes:
            for code in name_to_codes[query]:
                results.append({
                    "planilha_nome":    query,
                    "bq_nome":          query,
                    "partner_code":     code,
                    "score":            100,
                    "rfv_familia":      row['rfv_familia'],
                    "salesperson_name": row['salesperson_name'],
                    "aceito":           True,
                    "match_type":       "exact",
                })
        else:
            m = process.extractOne(query, partner_names, scorer=fuzz.WRatio)
            if m:
                bq_name, score, _ = m
                accepted = score >= FUZZY_THRESHOLD
                for code in name_to_codes.get(bq_name, []):
                    results.append({
                        "planilha_nome":    query,
                        "bq_nome":          bq_name,
                        "partner_code":     code,
                        "score":            score,
                        "rfv_familia":      row['rfv_familia'],
                        "salesperson_name": row['salesperson_name'],
                        "aceito":           accepted,
                        "match_type":       "fuzzy",
                    })
            else:
                results.append({
                    "planilha_nome":    query,
                    "bq_nome":         None,
                    "partner_code":    None,
                    "score":           0,
                    "rfv_familia":     row['rfv_familia'],
                    "salesperson_name": row['salesperson_name'],
                    "aceito":          False,
                    "match_type":      "none",
                })
    return pd.DataFrame(results)


# ── BQ truncate + insert ──────────────────────────────────────────────────────

def truncate_and_insert(client: bigquery.Client, rows: list) -> int:
    table_id = f"{BQ_PROJECT}.{DATASET_ID}.param_com_rfv_carteira"

    # TRUNCATE (DELETE WHERE TRUE)
    job = client.query(f"DELETE FROM `{table_id}` WHERE TRUE")
    job.result()
    print(f"  Tabela truncada.")

    # INSERT via load_table_from_json (sem limite de streaming)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = client.load_table_from_json(rows, table_id, job_config=job_config)
    job.result()
    if job.errors:
        print(f"  [erro] {job.errors[:3]}")
        return 0
    return len(rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 78)
    print("populate_carteira v2 — base completa (geral + atribuição por vendedor)")
    print("=" * 78)

    # 1. Montar DataFrames por família
    print("\n[1/4] Extraindo clientes das planilhas (base GERAL)...")
    hosp_df = build_familia_df("HOSPITALAR", HOSP_FILE, HOSP_GERAL_SHEET, HOSP_VENDEDOR_SHEETS)
    farm_df = build_familia_df("FARMACIAS",  FARM_FILE, FARM_GERAL_SHEET, FARM_VENDEDOR_SHEETS)
    sac_df  = build_familia_df("SAC",        SAC_FILE,  SAC_GERAL_SHEET,  SAC_VENDEDOR_SHEETS)
    todos   = pd.concat([hosp_df, farm_df, sac_df], ignore_index=True)

    print(f"\n  HOSPITALAR: {len(hosp_df)} | FARMACIAS: {len(farm_df)} | SAC: {len(sac_df)} | Total: {len(todos)}")

    # 2. Buscar parceiros no ERP
    print("\n[2/4] Buscando clientes ativos no ERP (SQL Server)...")
    conn        = erp_conn()
    partners_df = fetch_erp_partners(conn)
    conn.close()
    print(f"  {len(partners_df)} clientes ativos no ERP")

    # 3. Match planilha × ERP
    print(f"\n[3/4] Match planilha × ERP (threshold={FUZZY_THRESHOLD})...")
    matched    = match_clients(todos, partners_df)
    aceitos    = matched[matched['aceito'] == True].copy()
    rejeitados = matched[matched['aceito'] == False].copy()

    exact_count = len(aceitos[aceitos['match_type'] == 'exact'])
    fuzzy_count = len(aceitos[aceitos['match_type'] == 'fuzzy'])
    print(f"  Aceitos:    {len(aceitos):4d}  (exact={exact_count}, fuzzy={fuzzy_count})")
    print(f"  Rejeitados: {len(rejeitados):4d}")

    # Breakdown por família
    for familia in aceitos['rfv_familia'].unique():
        sub = aceitos[aceitos['rfv_familia'] == familia]
        uniq = sub['planilha_nome'].nunique()
        print(f"    {familia}: {uniq} clientes únicos")

    if len(rejeitados) > 0:
        print("\n  --- Rejeitados (top 30 por score) ---")
        for _, r in rejeitados.sort_values('score', ascending=False).head(30).iterrows():
            print(f"  {r['score']:3.0f} | '{r['planilha_nome']}' => '{r['bq_nome']}' | {r['rfv_familia']}/{r['salesperson_name']}")
        out_path = Path(__file__).parent / "carteira_rejeitados.csv"
        rejeitados.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"\n  Rejeitados salvos em: {out_path}")

    if len(aceitos) == 0:
        print("\n[aviso] Nenhum match aceito. Abortando.")
        return 1

    # 4. TRUNCATE + INSERT no BigQuery
    print(f"\n[4/4] Truncando e reinserindo {len(aceitos)} registros no BigQuery...")
    client = bq_client()

    rows_to_insert = [
        {
            "partner_code":     int(row['partner_code']),
            # Usa planilha_nome (Excel do Alves) como display name — o ERP armazena
            # caracteres especiais como '?' por collation Latin1; a planilha tem os
            # acentos corretos (ç, ã, etc.).
            "partner_name":     row['planilha_nome'],
            "rfv_familia":      row['rfv_familia'],
            "salesperson_name": row['salesperson_name'],
            "is_active":        True,
            "updated_at":       pd.Timestamp.utcnow().isoformat(),
        }
        for _, row in aceitos.iterrows()
    ]
    inserted = truncate_and_insert(client, rows_to_insert)
    print(f"  {inserted} registros inseridos com sucesso")

    print()
    print("=" * 78)
    print("PRÓXIMOS PASSOS:")
    print("  1. Revisar carteira_rejeitados.csv e inserir manualmente se necessário")
    print("  2. py -3 sql/silver_comercial/run_silver_comercial.py  ← rebuild silver")
    print("  3. Validar contagem: HOSPITALAR ~786, FARMACIAS ~248, SAC ~79")
    print("  4. Atribuir vendedor SAC quando definido (hoje: 'Sem Vendedor')")
    print("=" * 78)

    return 0 if inserted > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
