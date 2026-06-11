"""
populate_carteira_v3 — fonte: planilha "Carteira de Clientes - Inside Sales (Atualizado)"
                       + "Farmers Farmacias (version 1)".

Mudanças vs v2:
  - Match por ID ERP (chave primária na planilha, não precisa fuzzy)
  - 6 vendedores HOSPITALAR/SAC + 1 vendedor FARMACIAS (Cauã Ribeiro)
  - Regra Giovanna: Geovanna Gomes só pode aparecer em SAC (clientes dela na
    aba HOSPITALAR são reclassificados como SAC)
  - Inativa (is_active=FALSE) clientes da carteira atual que NÃO estão na nova
    planilha — mantém histórico em vez de apagar
  - Flag --dry-run: imprime contagens, NÃO escreve no BQ

Executar:
  py -3 sql/silver_comercial/populate_carteira_v3.py --dry-run
  py -3 sql/silver_comercial/populate_carteira_v3.py            # aplica de fato
"""
import io
import sys
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# Reaproveita helpers da v2
from populate_carteira import BQ_PROJECT, DATASET_ID, CREDS_BQ, bq_client, truncate_and_insert

# ── Fontes ────────────────────────────────────────────────────────────────────
INSIDE_SALES_FILE = (
    r"C:\Users\gusta\Downloads\Carteira de Clientes - Inside Sales (Atualizado).xlsx"
)
INSIDE_SALES_SHEET = "Planilha1"
INSIDE_SALES_HEADER_ROW = 14   # cabeçalho real na linha 15 do Excel

FARMACIA_FILE = (
    r"C:\Users\gusta\Downloads\Farmers Farmacias (version 1)"
    r"(Recuperado Automaticamente) (3) (1).xlsx"
)
FARMACIA_SHEET = "Carteira Farmer Farm. (Ribeiro)"
FARMACIA_HEADER_ROW = 3        # cabeçalho na linha 4 do Excel

# ── Mapeamentos oficiais (reunião 25/05/2026) ─────────────────────────────────
# Vendedor da planilha Inside Sales → Nome canônico para o BQ.
# Vendedor D vem vazio na planilha; Alves confirmou via WhatsApp = Kauan Ramos.
VENDEDOR_RAW_TO_NOME = {
    "Guilherme Aquino": "Guilherme Aquino",
    "Kauã Rodrigues":   "Kauã Rodrigues",
    "Richard Lucas":    "Richard Lucas",
    "Geovanna Gomes":   "Geovanna Gomes",
    "Eduardo Marques":  "Eduardo Marques",
    "0":                "Kauan Ramos",   # vendedor D (célula em branco)
    "":                 "Kauan Ramos",
    "nan":              "Kauan Ramos",
}

GIOVANNA = "Geovanna Gomes"
RIBEIRO  = "Cauã Ribeiro"

# Mapeamento canônico família → grupo ERP (espelha param_com_grupo_familia no silver).
# Confirmado por Frederico/DC-Info na reunião 27/05/2026.
FAMILIA_TO_GRUPO = {
    "HOSPITALAR": "FA",   # Farmer
    "FARMACIAS":  "FR",   # Farmácia
    "SAC":        "PC",   # Peças
}

# ── Redirecionamento Eduardo Marques ──────────────────────────────────────────
# Eduardo tem 83 clientes na planilha Inside Sales (R$ 1,03M de receita 2024+),
# mas a regra do silver (`build_silver_comercial.sql`) exclui esse vendedor do
# RFV de carteira ativa (era licitação). O Alves indicou que esses clientes
# foram redirecionados para outros vendedores — aguarda confirmação caso a caso.
#
# Para ATIVAR o redirecionamento, preencher uma das opções abaixo:
#   1) EDUARDO_REDIRECT_DEFAULT = "Guilherme Aquino"  → todos os 83 vão pra ele
#   2) EDUARDO_REDIRECT_BY_ID   = { id_erp: "Novo Vendedor", ... }  → por cliente
#
# Quando ambos estiverem preenchidos, BY_ID tem prioridade sobre DEFAULT.
# Clientes sem destino caem em DEFAULT; se DEFAULT for None, ficam como
# Eduardo Marques (e continuam excluídos do RFV pelo filtro do silver).
EDUARDO_NOME = "Eduardo Marques"
EDUARDO_REDIRECT_DEFAULT: str | None = None
EDUARDO_REDIRECT_BY_ID: dict[int, str] = {
    # Top 10 por receita 2024+ (preencher após confirmação do Alves):
    # 4115:  "?",  # Altermed Material Medico Hospitalar Ltda.        — R$ 76.618,83
    # 33394: "?",  # Idm Solucoes Publicas Ltda                        — R$ 67.475,25
    # 31599: "?",  # Hd-Miyahara Comercio E Serviços Ltda              — R$ 61.009,93
    # 46152: "?",  # Squadra Do Brasil Distribuidora                   — R$ 56.149,96
    # 50860: "?",  # Vita Solucoes Em Engenharia Clinica Ltda          — R$ 52.432,99
    # 19796: "?",  # Equipos Comercial Ltda                            — R$ 48.181,90
    # 8582:  "?",  # A C P Correa E Cia Ltda                           — R$ 47.828,73
    # 8552:  "?",  # Cirurgica Uniao Ltda                              — R$ 35.805,54
    # 7266:  "?",  # Cirurgica Paulista Com Mat Med Hosp Ltda          — R$ 33.826,41
    # 50364: "?",  # New Medca Comercio E Assistencia Tecnica Ltda     — R$ 33.566,72
}


def aplicar_redirect_eduardo(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Substitui Eduardo Marques pelo vendedor de destino, quando configurado.

    Retorna o df com a coluna `vendedor_nome` atualizada e um dict de stats
    para o relatório (quantos foram redirecionados, quantos ficaram).
    """
    mask = df['vendedor_nome'] == EDUARDO_NOME
    total_eduardo = int(mask.sum())
    if total_eduardo == 0:
        return df, {'eduardo_total': 0, 'redirecionados': 0, 'mantidos': 0}

    def _destino(id_erp: int) -> str:
        if id_erp in EDUARDO_REDIRECT_BY_ID:
            return EDUARDO_REDIRECT_BY_ID[id_erp]
        if EDUARDO_REDIRECT_DEFAULT is not None:
            return EDUARDO_REDIRECT_DEFAULT
        return EDUARDO_NOME

    df = df.copy()
    df.loc[mask, 'vendedor_nome'] = df.loc[mask, 'id_erp'].apply(_destino)
    redirecionados = int((df.loc[mask, 'vendedor_nome'] != EDUARDO_NOME).sum())
    return df, {
        'eduardo_total':    total_eduardo,
        'redirecionados':   redirecionados,
        'mantidos':         total_eduardo - redirecionados,
    }


# ── Carregadores ──────────────────────────────────────────────────────────────

def load_inside_sales() -> pd.DataFrame:
    """Retorna df com colunas: id_erp, partner_name, vendedor_nome, rfv_familia."""
    df = pd.read_excel(INSIDE_SALES_FILE, sheet_name=INSIDE_SALES_SHEET, header=INSIDE_SALES_HEADER_ROW)
    df = df[['ID ERP', 'Razão Social', 'Vendedor Responsável']].copy()
    df.columns = ['id_erp', 'partner_name', 'vendedor_raw']
    df['id_erp'] = pd.to_numeric(df['id_erp'], errors='coerce').astype('Int64')
    df = df.dropna(subset=['id_erp'])
    df['vendedor_raw'] = df['vendedor_raw'].fillna(0).astype(str).str.strip()
    df['vendedor_nome'] = df['vendedor_raw'].map(VENDEDOR_RAW_TO_NOME).fillna(df['vendedor_raw'])
    df, redirect_stats = aplicar_redirect_eduardo(df)
    df.attrs['redirect_stats'] = redirect_stats
    # Inside Sales é Hospitalar — exceto Giovanna (regra acordada na reunião 25/05).
    df['rfv_familia'] = df['vendedor_nome'].apply(
        lambda v: 'SAC' if v == GIOVANNA else 'HOSPITALAR'
    )
    return df[['id_erp', 'partner_name', 'vendedor_nome', 'rfv_familia']]


def load_farmacia() -> pd.DataFrame:
    df = pd.read_excel(FARMACIA_FILE, sheet_name=FARMACIA_SHEET, header=FARMACIA_HEADER_ROW)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[['ID ERP', 'Razão Social']].copy()
    df.columns = ['id_erp', 'partner_name']
    df['id_erp'] = pd.to_numeric(df['id_erp'], errors='coerce').astype('Int64')
    df = df.dropna(subset=['id_erp'])
    df['vendedor_nome'] = RIBEIRO
    df['rfv_familia']   = 'FARMACIAS'
    return df


def load_carteira_atual(client: bigquery.Client) -> pd.DataFrame:
    """Carteira ativa atual no BQ — para identificar quem será inativado."""
    df = client.query(f"""
        SELECT partner_code AS id_erp, partner_name, rfv_familia, salesperson_name
        FROM `{BQ_PROJECT}.{DATASET_ID}.param_com_rfv_carteira`
        WHERE is_active = TRUE
    """).to_dataframe()
    df['id_erp'] = df['id_erp'].astype('Int64')
    return df


# ── Pipeline ──────────────────────────────────────────────────────────────────

def build_rows() -> tuple[list, list, dict]:
    """
    Constrói linhas para inserção no BQ.

    Retorna:
      rows_ativos   → lista de dicts com is_active=True (clientes da nova carteira)
      rows_inativos → lista de dicts com is_active=False (96 que sairam)
      stats         → dict de contagens p/ relatório
    """
    print("[1/4] Lendo Inside Sales (Hospitalar + SAC)...")
    df_is = load_inside_sales()
    print(f"  {len(df_is)} linhas (após drop NA em ID ERP)")
    rstats = df_is.attrs.get('redirect_stats', {})
    if rstats.get('eduardo_total', 0):
        print(
            f"  Eduardo Marques: {rstats['eduardo_total']} clientes na planilha → "
            f"{rstats['redirecionados']} redirecionados, "
            f"{rstats['mantidos']} sem destino configurado "
            "(ficam como Eduardo Marques e são excluídos do RFV pelo filtro do silver)."
        )
        if rstats['mantidos'] > 0 and EDUARDO_REDIRECT_DEFAULT is None:
            print(
                "  ⚠  Preencher EDUARDO_REDIRECT_DEFAULT ou EDUARDO_REDIRECT_BY_ID "
                "no topo deste arquivo após o Alves confirmar o destino."
            )
    print("  Vendedores:")
    print(df_is['vendedor_nome'].value_counts().to_string())
    print("  Famílias (após regra Giovanna→SAC):")
    print(df_is.groupby(['rfv_familia', 'vendedor_nome']).size().to_string())

    print("\n[2/4] Lendo Farmers Farmácia (Cauã Ribeiro)...")
    df_fa = load_farmacia()
    print(f"  {len(df_fa)} linhas")

    # Junta e dedup por (id_erp, rfv_familia) — mesmo ID pode estar em duas famílias
    # se for legítimo. Pequeno cuidado: se mesmo id estiver em IS e Farma, mantemos as
    # duas linhas (HOSPITALAR e FARMACIAS).
    df_nova = pd.concat([df_is, df_fa], ignore_index=True)
    df_nova = df_nova.drop_duplicates(subset=['id_erp', 'rfv_familia'], keep='first')
    print(f"\n[3/4] Total carteira nova (id_erp × rfv_familia únicos): {len(df_nova)}")
    print(f"  Únicos por id_erp: {df_nova['id_erp'].nunique()}")

    print("\n[4/4] Conectando no BQ p/ identificar os 96 a inativar...")
    client = bq_client()
    df_atual = load_carteira_atual(client)
    ids_novos = set(df_nova['id_erp'].dropna().astype(int))
    ids_atuais = set(df_atual['id_erp'].dropna().astype(int))
    ids_inativar = sorted(ids_atuais - ids_novos)
    print(f"  Carteira atual:    {len(ids_atuais)} clientes ativos")
    print(f"  IDs em ambos:      {len(ids_atuais & ids_novos)}")
    print(f"  Só na nova:        {len(ids_novos - ids_atuais)}  (entram como novos)")
    print(f"  Só na atual:       {len(ids_inativar)}  (vão para is_active=FALSE)")

    now_iso = pd.Timestamp.utcnow().isoformat()

    rows_ativos = [
        {
            "partner_code":           int(r['id_erp']),
            "partner_name":           str(r['partner_name']),
            "rfv_familia":            r['rfv_familia'],
            "salesperson_name":       r['vendedor_nome'],
            "salesperson_group_code": FAMILIA_TO_GRUPO.get(r['rfv_familia']),
            "is_active":              True,
            "updated_at":             now_iso,
        }
        for _, r in df_nova.iterrows()
    ]

    # Os 96 inativados: pega a row original da carteira atual e marca is_active=False
    df_inat = df_atual[df_atual['id_erp'].isin(ids_inativar)].copy()
    rows_inativos = [
        {
            "partner_code":           int(r['id_erp']),
            "partner_name":           str(r['partner_name']),
            "rfv_familia":            r['rfv_familia'],
            "salesperson_name":       r['salesperson_name'],
            "salesperson_group_code": FAMILIA_TO_GRUPO.get(r['rfv_familia']),
            "is_active":              False,
            "updated_at":             now_iso,
        }
        for _, r in df_inat.iterrows()
    ]

    stats = {
        'ativos':          len(rows_ativos),
        'inativos':        len(rows_inativos),
        'total':           len(rows_ativos) + len(rows_inativos),
        'unique_ids':      df_nova['id_erp'].nunique(),
        'novos_pra_add':   len(ids_novos - ids_atuais),
        'matches':         len(ids_atuais & ids_novos),
    }
    return rows_ativos, rows_inativos, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true',
                        help='Só imprime contagens, não escreve no BigQuery.')
    args = parser.parse_args()

    print("=" * 78)
    print("populate_carteira v3 — fonte: Inside Sales (Atualizado) + Farmers Farmácia")
    if args.dry_run:
        print(">>> MODO DRY-RUN — BQ não será modificado <<<")
    print("=" * 78)

    rows_ativos, rows_inativos, stats = build_rows()

    print()
    print("=" * 78)
    print("RESUMO")
    print("=" * 78)
    print(f"  Ativos (nova carteira):    {stats['ativos']}")
    print(f"  Inativos (saíram):         {stats['inativos']}")
    print(f"  Total a inserir:           {stats['total']}")
    print(f"  Carteira atual (matches):  {stats['matches']}")
    print(f"  Novos pra adicionar:       {stats['novos_pra_add']}")

    if args.dry_run:
        print("\n[dry-run] Nada gravado. Tire a flag --dry-run para aplicar.")
        return 0

    print("\n[BQ] Truncando e reinserindo carteira completa...")
    client = bq_client()
    rows_all = rows_ativos + rows_inativos
    inserted = truncate_and_insert(client, rows_all)
    print(f"  {inserted} registros inseridos com sucesso "
          f"({stats['ativos']} ativos + {stats['inativos']} inativos)")

    print()
    print("=" * 78)
    print("PRÓXIMOS PASSOS:")
    print("  1. Rodar rebuild histórico do RFV:")
    print("     py -3 sql/silver_comercial/run_rfv_full_rebuild.py")
    print("  2. Validar no dashboard (localhost:8080) os totais por vendedor")
    print("  3. Mandar print para o Alves confirmando aplicação")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
