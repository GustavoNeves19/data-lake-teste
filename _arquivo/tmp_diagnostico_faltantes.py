"""
Diagnóstico profundo — clientes faltantes no RFV vs planilha Alves (abril/2026).

Para cada cliente que está na planilha do Alves mas NÃO aparece no nosso resultado,
rastreia em qual etapa do pipeline ele foi perdido:

  CAMADA 1 — Fuzzy match falhou (não entrou em param_com_rfv_carteira)
  CAMADA 2 — Entrou na carteira mas partner_code sem nenhum pedido no período
  CAMADA 3 — Tem pedidos mas todos fora do status 3/4
  CAMADA 4 — Tem pedidos status 3/4 mas natureza NÃO financeira (financial_flag ≠ 'F')
  CAMADA 5 — Tem tudo certo mas sumiu por outro motivo (bug, duplicata, salesperson filter)

Janela fixa: 01/04/2025 → 30/04/2026  |  Ref: 30/04/2026
"""
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
from pathlib import Path
from google.cloud import bigquery
from google.oauth2 import service_account
from rapidfuzz import process, fuzz
import pyodbc, os
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
_dir = Path(__file__).resolve()
for _ in range(8):
    _dir = _dir.parent
    if (_dir / ".env").exists():
        load_dotenv(_dir / ".env")
        break

PROJ       = "sapient-metrics-492914-m7"
DATA_INI   = "2025-04-01"
DATA_FIM   = "2026-04-30"
DATA_REF   = "2026-04-30"
CREDS_BQ   = r"C:\teste\sapient-metrics.json"
FUZZY_THR  = 88

HOSP_FILE  = r"C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026 (1).xlsx"
SAC_FILE   = r"C:\Users\gusta\Downloads\RFV SAC 01-04-2025 até 30-04-2026 (1).xlsx"
HOSP_GERAL = "Sem fórmula Geral"
SAC_GERAL  = "Sem Fórmula"

OUTPUT_CSV = Path(__file__).parent / "diagnostico_faltantes.csv"

# ── Clientes ──────────────────────────────────────────────────────────────────

def extract_planilha_clients(filepath, sheet_name):
    xls = pd.ExcelFile(filepath)
    if sheet_name not in xls.sheet_names:
        raise ValueError(f"Aba '{sheet_name}' não encontrada em {Path(filepath).name}")
    df  = pd.read_excel(filepath, sheet_name=sheet_name)
    col = df.columns[0]
    nomes = df[col].dropna().astype(str).str.strip().unique()
    return [n for n in nomes if n and n.upper() not in ('ID - CLIENTE', 'NAN', '')]


def bq_client():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_BQ, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return bigquery.Client(credentials=creds, project=PROJ)


def erp_conn():
    cs = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.getenv('SQL_SERVER_HOST')},{os.getenv('SQL_SERVER_PORT')};"
        f"DATABASE={os.getenv('SQL_SERVER_DATABASE')};"
        f"UID={os.getenv('SQL_SERVER_USER')};"
        f"PWD={os.getenv('SQL_SERVER_PASSWORD')};"
    )
    return pyodbc.connect(cs, timeout=30)


def fetch_erp_partners(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT YCODCLI, YNOMCLI FROM [CLIENTES OU FORNECEDORES] WHERE YTIPCLI = 'C'")
    data = [(int(r[0]), str(r[1]).strip()) for r in cur.fetchall() if r[0] and r[1]]
    return pd.DataFrame(data, columns=['partner_code', 'partner_name'])


# ── Pipeline BigQuery ──────────────────────────────────────────────────────────

def fetch_carteira(client):
    """Todos os registros na carteira (incluindo Eduardo/Karina — sem filtro)."""
    sql = f"""
    SELECT partner_code, partner_name, rfv_familia, salesperson_name, is_active
    FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
    """
    return client.query(sql).to_dataframe()


def fetch_all_orders_for_codes(client, partner_codes):
    """Pedidos de qualquer status/natureza para os partner_codes informados."""
    if not partner_codes:
        return pd.DataFrame()
    codes_str = ", ".join(str(c) for c in partner_codes)
    sql = f"""
    SELECT
        o.partner_code,
        o.order_number,
        o.order_date,
        o.order_status,
        o.total_amount,
        o.nature_code,
        n.financial_flag
    FROM `{PROJ}.dm_orders.fact_sales_order` o
    LEFT JOIN `{PROJ}.dm_orders.dim_operation_nature` n
        ON n.nature_code = o.nature_code
    WHERE o.partner_code IN ({codes_str})
      AND o.order_date BETWEEN DATE('{DATA_INI}') AND DATE('{DATA_FIM}')
    ORDER BY o.partner_code, o.order_date
    """
    return client.query(sql).to_dataframe()


def fetch_rfv_result(client):
    """Resultado RFV real (mesma query do tmp_valida_abril mas retorna linhas individuais)."""
    sql = f"""
    WITH vendas AS (
      SELECT
        o.partner_code,
        c.partner_name
      FROM `{PROJ}.dm_orders.fact_sales_order` o
      JOIN `{PROJ}.silver_comercial.param_com_rfv_carteira` c
        ON  c.partner_code = o.partner_code
        AND c.is_active    = TRUE
        AND c.salesperson_name NOT IN ('Eduardo', 'Karina')
      JOIN `{PROJ}.dm_orders.dim_operation_nature` n
        ON  n.nature_code    = o.nature_code
        AND n.financial_flag = 'F'
      WHERE o.order_status IN (3, 4)
        AND o.order_date BETWEEN DATE('{DATA_INI}') AND DATE('{DATA_FIM}')
    )
    SELECT DISTINCT partner_name
    FROM vendas
    """
    df = client.query(sql).to_dataframe()
    return set(df['partner_name'].tolist())


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def diagnosticar(familia, planilha_clientes, carteira_df, partners_df, orders_df, rfv_names):
    """
    Para cada cliente do Alves que não está no resultado RFV, classifica a causa.
    Retorna lista de dicts com detalhes.
    """
    # Mapa de nomes ERP → codes
    name_to_code = {}
    for _, r in partners_df.iterrows():
        name_to_code.setdefault(r['partner_name'], []).append(r['partner_code'])
    erp_names = partners_df['partner_name'].tolist()

    # Carteira desta família (sem filtro de vendedor)
    cart_familia = carteira_df[carteira_df['rfv_familia'] == familia]
    cart_codes   = set(cart_familia['partner_code'].tolist())

    rows = []
    for planilha_nome in sorted(planilha_clientes):
        # Se já está no resultado RFV → OK, pula
        # Tenta match exato no resultado final pelo nome da planilha
        # (usamos bq_nome da carteira como proxy)
        cart_match = cart_familia[cart_familia['partner_name'].str.upper() == planilha_nome.upper()]

        in_rfv = False
        if not cart_match.empty:
            bq_nome = cart_match.iloc[0]['partner_name']
            in_rfv = bq_nome in rfv_names

        if in_rfv:
            continue  # cliente presente no resultado — não é faltante

        # ── Diagnóstico em camadas ────────────────────────────────────────────
        row = {
            "familia":       familia,
            "planilha_nome": planilha_nome,
            "camada":        None,
            "causa":         None,
            "bq_nome":       None,
            "partner_code":  None,
            "fuzzy_score":   None,
            "n_pedidos_total": 0,
            "n_pedidos_34":    0,
            "n_pedidos_fin":   0,
            "fat_potencial":   0.0,
            "fat_excluido_status":  0.0,
            "fat_excluido_nature":  0.0,
            "salesperson":   None,
            "is_active":     None,
        }

        # CAMADA 1 — Fuzzy match
        if planilha_nome in name_to_code:
            bq_nome = planilha_nome
            score   = 100
            codes   = name_to_code[planilha_nome]
            match_type = "exact"
        else:
            m = process.extractOne(planilha_nome, erp_names, scorer=fuzz.WRatio)
            if m:
                bq_nome, score, _ = m
                codes   = name_to_code.get(bq_nome, [])
                match_type = "fuzzy"
            else:
                bq_nome, score, codes, match_type = None, 0, [], "none"

        row["fuzzy_score"] = score
        row["bq_nome"]     = bq_nome

        if score < FUZZY_THR or not codes:
            row["camada"] = 1
            row["causa"]  = f"Fuzzy match falhou (score={score:.0f} < {FUZZY_THR})"
            rows.append(row)
            continue

        # CAMADA 1b — bq_nome está na carteira desta família?
        cart_this = cart_familia[cart_familia['partner_name'] == bq_nome]
        if cart_this.empty:
            row["camada"]      = 1
            row["causa"]       = f"Match OK (score={score:.0f}) mas NÃO inserido na carteira (família={familia})"
            row["partner_code"] = codes[0]
            rows.append(row)
            continue

        code = int(cart_this.iloc[0]['partner_code'])
        row["partner_code"] = code
        row["salesperson"]  = cart_this.iloc[0]['salesperson_name']
        row["is_active"]    = cart_this.iloc[0]['is_active']

        # Filtrar pedidos deste código
        ped = orders_df[orders_df['partner_code'] == code].copy()
        row["n_pedidos_total"] = len(ped)

        # CAMADA 2 — Sem nenhum pedido no período
        if ped.empty:
            row["camada"] = 2
            row["causa"]  = "Carteira OK mas zero pedidos no período (01/04/2025→30/04/2026)"
            rows.append(row)
            continue

        # CAMADA 3 — Pedidos existem mas nenhum com status 3 ou 4
        ped34 = ped[ped['order_status'].isin([3, 4])]
        row["n_pedidos_34"]        = len(ped34)
        row["fat_excluido_status"] = float(ped[~ped['order_status'].isin([3, 4])]['total_amount'].sum())

        if ped34.empty:
            statuses = sorted(ped['order_status'].unique().tolist())
            row["camada"] = 3
            row["causa"]  = f"Pedidos encontrados mas status ≠ 3/4 (status={statuses})"
            rows.append(row)
            continue

        # CAMADA 4 — Pedidos 3/4 existem mas natureza não financeira
        ped_fin = ped34[ped34['financial_flag'] == 'F']
        row["n_pedidos_fin"]       = len(ped_fin)
        row["fat_excluido_nature"] = float(ped34[ped34['financial_flag'] != 'F']['total_amount'].sum())
        row["fat_potencial"]       = float(ped_fin['total_amount'].sum())

        if ped_fin.empty:
            natures = sorted(ped34['nature_code'].unique().tolist())
            row["camada"] = 4
            row["causa"]  = f"Pedidos status 3/4 OK mas financial_flag ≠ F (natures={natures})"
            rows.append(row)
            continue

        # CAMADA 5 — Deveria estar no resultado mas não está
        # Possíveis causas: salesperson IN ('Eduardo','Karina'), is_active=False, duplicata de nome
        motivos = []
        if str(row["salesperson"]) in ('Eduardo', 'Karina'):
            motivos.append(f"salesperson='{row['salesperson']}' filtrado")
        if not row["is_active"]:
            motivos.append("is_active=False")
        if not motivos:
            motivos.append("causa desconhecida (verificar manualmente)")
        row["fat_potencial"] = float(ped_fin['total_amount'].sum())
        row["camada"] = 5
        row["causa"]  = " | ".join(motivos)
        rows.append(row)

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("  DIAGNÓSTICO PROFUNDO — Clientes faltantes vs planilha Alves (abril/2026)")
    print(f"  Janela: {DATA_INI} → {DATA_FIM}  |  Ref: {DATA_REF}")
    print("=" * 72)

    print("\n[1/5] Lendo planilhas do Alves...")
    hosp_clientes = extract_planilha_clients(HOSP_FILE, HOSP_GERAL)
    sac_clientes  = extract_planilha_clients(SAC_FILE,  SAC_GERAL)
    print(f"  HOSPITALAR: {len(hosp_clientes)} clientes | SAC: {len(sac_clientes)} clientes")

    print("\n[2/5] Conectando ao ERP e BigQuery...")
    conn        = erp_conn()
    partners_df = fetch_erp_partners(conn)
    conn.close()
    bq = bq_client()
    carteira_df = fetch_carteira(bq)
    rfv_names   = fetch_rfv_result(bq)
    print(f"  ERP: {len(partners_df)} parceiros | Carteira BQ: {len(carteira_df)} registros | RFV result: {len(rfv_names)} nomes únicos")

    print("\n[3/5] Buscando todos os pedidos dos clientes da carteira...")
    all_codes = list(set(carteira_df['partner_code'].tolist()))
    orders_df = fetch_all_orders_for_codes(bq, all_codes)
    print(f"  {len(orders_df)} pedidos encontrados para {orders_df['partner_code'].nunique() if not orders_df.empty else 0} códigos")

    print("\n[4/5] Diagnosticando clientes faltantes...")
    resultados = []
    for familia, clientes in [("HOSPITALAR", hosp_clientes), ("SAC", sac_clientes)]:
        linhas = diagnosticar(familia, clientes, carteira_df, partners_df, orders_df, rfv_names)
        resultados.extend(linhas)
        print(f"  {familia}: {len(clientes)} na planilha → {len(linhas)} faltantes diagnosticados")

    if not resultados:
        print("\n  ✅ Nenhum cliente faltante encontrado!")
        return 0

    df_out = pd.DataFrame(resultados)

    # ── Relatório ─────────────────────────────────────────────────────────────
    print("\n[5/5] Relatório por camada")
    print("=" * 72)

    total_fat_risco = 0.0

    for familia in ["HOSPITALAR", "SAC"]:
        sub = df_out[df_out["familia"] == familia]
        if sub.empty:
            continue

        fat_risco = float(sub["fat_potencial"].sum())
        total_fat_risco += fat_risco

        print(f"\n{'─'*72}")
        print(f"  {familia}  — {len(sub)} clientes faltantes  |  R$ {fat_risco:,.2f} faturamento potencial")
        print(f"{'─'*72}")

        for camada in sorted(sub["camada"].unique()):
            grupo = sub[sub["camada"] == camada]
            fat_g = float(grupo["fat_potencial"].sum())
            print(f"\n  CAMADA {camada} — {len(grupo)} clientes  |  R$ {fat_g:,.2f} potencial")

            camada_labels = {
                1: "Fuzzy match falhou / não entrou na carteira",
                2: "Na carteira mas sem pedidos no período",
                3: "Pedidos existem mas status ≠ 3/4",
                4: "Pedidos 3/4 existem mas natureza não financeira",
                5: "Deveria estar — filtro de vendedor / is_active / outro",
            }
            print(f"  {'Planilha':<40} {'BQ Nome':<40} {'Score':>5}  {'Causa'}")
            print(f"  {'─'*40} {'─'*40} {'─'*5}  {'─'*35}")
            for _, r in grupo.sort_values("fat_potencial", ascending=False).iterrows():
                bq  = str(r['bq_nome'])[:39] if r['bq_nome'] else "(sem match)"
                fat = f"R${float(r['fat_potencial']):>10,.0f}" if float(r['fat_potencial']) > 0 else "          R$0"
                print(f"  {str(r['planilha_nome'])[:40]:<40} {bq:<40} {int(r['fuzzy_score'] or 0):>5}  {fat}  {r['causa']}")

    print(f"\n{'='*72}")
    print(f"  TOTAL FATURAMENTO EM RISCO:  R$ {total_fat_risco:,.2f}")
    print(f"{'='*72}")

    # ── Resumo ────────────────────────────────────────────────────────────────
    print("\n  RESUMO EXECUTIVO (causa raiz × impacto)")
    print(f"  {'Camada':<60} {'Clientes':>8}  {'R$ Potencial':>14}")
    print(f"  {'─'*60} {'─'*8}  {'─'*14}")
    for camada in sorted(df_out["camada"].unique()):
        desc = {
            1: "Fuzzy match / não na carteira",
            2: "Sem pedidos no período",
            3: "Pedidos com status errado (não 3/4)",
            4: "Natureza não financeira (flag ≠ F)",
            5: "Filtro vendedor / is_active / outro",
        }.get(camada, f"Camada {camada}")
        g   = df_out[df_out["camada"] == camada]
        fat = float(g["fat_potencial"].sum())
        print(f"  {desc:<60} {len(g):>8}  R$ {fat:>11,.0f}")

    df_out.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"\n  Detalhe completo salvo em: {OUTPUT_CSV}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
