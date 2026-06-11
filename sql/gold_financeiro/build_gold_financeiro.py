"""
build_gold_financeiro.py
Cria as tabelas Gold do setor Financeiro no BigQuery (Fase 1 minimalista).

Fonte:  sapient-metrics-492914-m7.silver_financeiro.slv_fin_resumo_mensal
Destino: sapient-metrics-492914-m7.gold_financeiro.{gold_fin_dre_mensal,
                                                     gold_fin_kpis_mensais}

Execucao:
    py -3 sql/gold_financeiro/build_gold_financeiro.py
"""

import sys
import io
import os
from google.cloud import bigquery
from google.oauth2 import service_account

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT = "sapient-metrics-492914-m7"
DATASET = "gold_financeiro"
LOCATION = "us-east1"
SILVER = f"{PROJECT}.silver_financeiro"
GOLD = f"{PROJECT}.{DATASET}"

CREDS_PATHS = [
    r"C:\teste\sapient-metrics.json",
    r"C:\teste\credentials.json",
    r"C:\teste\nevoni-credentials.json",
    r"C:\teste\service-account.json",
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
]


def get_client():
    for p in CREDS_PATHS:
        if p and os.path.isfile(p):
            creds = service_account.Credentials.from_service_account_file(
                p, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            return bigquery.Client(credentials=creds, project=PROJECT)
    return bigquery.Client(project=PROJECT)


def run(client, sql: str, label: str):
    print(f"  -> {label} ... ", end="", flush=True)
    job = client.query(sql)
    job.result()
    print("OK")


# Ordem de exibicao dos grupos DRE (confirmada com Diego 12/05/2026)
ORDEM_DRE = {
    "FATURAMENTO":               1,
    "IMPOSTOS S/ VENDAS":        2,
    "CUSTOS VARIÁVEIS DIRETOS":  3,
    "DESPESAS FIXAS":            5,
    "DESPESAS COMERCIAIS":       6,
    "MARKETING":                 7,
    "INVESTIMENTOS":             9,
    "MOVIMENTACAO INTRAGRUPO":   10,
    "FORA DO P&L":               11,
    "ATIVIDADES FINANCEIRAS":    12,
}

ORDEM_CASE = "\n".join(
    f"    WHEN '{g}' THEN {n}" for g, n in ORDEM_DRE.items()
)


def main():
    client = get_client()

    print(f"[0] Garantindo dataset {DATASET} em {LOCATION} ...")
    ds = bigquery.Dataset(f"{PROJECT}.{DATASET}")
    ds.location = LOCATION
    client.create_dataset(ds, exists_ok=True)
    print("    OK")

    print("\n[1] Criando tabelas Gold Financeiro (Fase 1) ...")

    # gold_fin_dre_mensal
    # Grain: regime x grupo_dre x subgroup x mes x company_code
    # Fonte: slv_fin_resumo_mensal (status = REALIZADO)
    # Sinal: CREDIT (+), DEBIT (-)
    run(client, f"""
CREATE OR REPLACE TABLE `{GOLD}.gold_fin_dre_mensal`
CLUSTER BY regime, grupo_dre
AS
SELECT
  PARSE_DATE('%Y-%m', rm.year_month)                        AS mes,
  rm.regime,
  rm.group_name                                             AS grupo_dre,
  COALESCE(rm.subgroup, rm.group_name)                      AS descricao,
  rm.company_code,
  CASE
    WHEN rm.account_sign = 'CREDIT' THEN  rm.amount
    WHEN rm.account_sign = 'DEBIT'  THEN -rm.amount
    ELSE rm.amount
  END                                                       AS valor,
  CASE rm.group_name
{ORDEM_CASE}
    ELSE 99
  END                                                       AS ordem_exibicao,
  rm.title_count,
  CURRENT_TIMESTAMP()                                       AS etl_loaded_at
FROM `{SILVER}.slv_fin_resumo_mensal` rm
WHERE rm.status = 'REALIZADO'
  AND SAFE.PARSE_DATE('%Y-%m', rm.year_month) IS NOT NULL
  AND SAFE.PARSE_DATE('%Y-%m', rm.year_month) <= DATE_TRUNC(CURRENT_DATE('America/Sao_Paulo'), MONTH)
""", "gold_fin_dre_mensal")

    # gold_fin_kpis_mensais
    # Grain: regime x mes
    # Deriva da gold_fin_dre_mensal (mesma fonte de verdade)
    run(client, f"""
CREATE OR REPLACE TABLE `{GOLD}.gold_fin_kpis_mensais`
CLUSTER BY regime
AS
WITH base AS (
  SELECT
    mes,
    regime,
    grupo_dre,
    SUM(valor) AS valor
  FROM `{GOLD}.gold_fin_dre_mensal`
  GROUP BY mes, regime, grupo_dre
)
SELECT
  mes,
  regime,
  SUM(CASE WHEN grupo_dre = 'FATURAMENTO'              THEN valor ELSE 0 END) AS faturamento,
  SUM(CASE WHEN grupo_dre = 'IMPOSTOS S/ VENDAS'       THEN valor ELSE 0 END) AS impostos_vendas,
  SUM(CASE WHEN grupo_dre = 'CUSTOS VARIÁVEIS DIRETOS' THEN valor ELSE 0 END) AS custos_variaveis,
  SUM(CASE WHEN grupo_dre = 'DESPESAS FIXAS'           THEN valor ELSE 0 END) AS despesas_fixas,
  SUM(CASE WHEN grupo_dre = 'DESPESAS COMERCIAIS'      THEN valor ELSE 0 END) AS despesas_comerciais,
  SUM(CASE WHEN grupo_dre = 'MARKETING'                THEN valor ELSE 0 END) AS marketing,

  -- Margem Bruta = Faturamento + Impostos (negativos) + Custos Variaveis (negativos)
  SUM(CASE WHEN grupo_dre = 'FATURAMENTO'              THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'IMPOSTOS S/ VENDAS'     THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'CUSTOS VARIÁVEIS DIRETOS' THEN valor ELSE 0 END) AS margem_bruta,

  -- EBITDA = Margem Bruta + Despesas Operacionais
  SUM(CASE WHEN grupo_dre = 'FATURAMENTO'              THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'IMPOSTOS S/ VENDAS'     THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'CUSTOS VARIÁVEIS DIRETOS' THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'DESPESAS FIXAS'         THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'DESPESAS COMERCIAIS'    THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'MARKETING'              THEN valor ELSE 0 END) AS ebitda,

  -- Lucro Liquido = EBITDA + Investimentos + Atividades Financeiras
  SUM(CASE WHEN grupo_dre = 'FATURAMENTO'              THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'IMPOSTOS S/ VENDAS'     THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'CUSTOS VARIÁVEIS DIRETOS' THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'DESPESAS FIXAS'         THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'DESPESAS COMERCIAIS'    THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'MARKETING'              THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'INVESTIMENTOS'          THEN valor ELSE 0 END)
  + SUM(CASE WHEN grupo_dre = 'ATIVIDADES FINANCEIRAS' THEN valor ELSE 0 END) AS lucro_liquido,

  CURRENT_TIMESTAMP() AS etl_loaded_at
FROM base
GROUP BY mes, regime
""", "gold_fin_kpis_mensais")

    print("\nTabelas Gold (Fase 1) criadas com sucesso.")
    print(f"   Dataset: {GOLD}")
    print("   Tabelas:")
    print("     - gold_fin_dre_mensal")
    print("     - gold_fin_kpis_mensais")
    print("\n   Abra o dashboard e recarregue a pagina Financeiro.")


if __name__ == "__main__":
    main()
