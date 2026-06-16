"""
Valida metodologia RFV contra planilha Alves — abril/2026.
Janela fixa: 01/04/2025 → 30/04/2026
Ref. recência: 30/04/2026
Não altera nenhuma tabela de produção.
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    r"C:\teste\sapient-metrics.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project="sapient-metrics-492914-m7")

PROJ = "sapient-metrics-492914-m7"
DATA_INI = "2025-04-01"
DATA_FIM = "2026-04-30"
DATA_REF = "2026-04-30"   # referência para calcular recência

sql = f"""
WITH vendas AS (
  SELECT
    o.partner_code,
    c.partner_name,
    c.rfv_familia,
    c.salesperson_name  AS rfv_salesperson,
    o.order_number,
    o.order_date,
    o.total_amount
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
),

rfv_base AS (
  SELECT
    partner_name,
    rfv_familia,
    rfv_salesperson,
    MAX(order_date)                                          AS ultima_compra,
    DATE_DIFF(DATE('{DATA_REF}'), MAX(order_date), DAY)     AS recencia_dias,
    COUNT(DISTINCT order_number)                             AS frequencia,
    ROUND(SUM(total_amount), 2)                              AS valor_total
  FROM vendas
  GROUP BY partner_name, rfv_familia, rfv_salesperson
),

scored AS (
  SELECT
    b.*,
    CASE
      WHEN b.rfv_familia IN ('HOSPITALAR', 'SAC') THEN
        CASE
          WHEN b.frequencia >= 5 THEN 'F1'
          WHEN b.frequencia  = 4 THEN 'F2'
          WHEN b.frequencia  = 3 THEN 'F3'
          WHEN b.frequencia  = 2 THEN 'F4'
          ELSE 'F5'
        END
      ELSE  -- FARMACIAS
        CASE
          WHEN b.frequencia >= 7 THEN 'F1'
          WHEN b.frequencia >= 5 THEN 'F2'
          WHEN b.frequencia >= 3 THEN 'F3'
          WHEN b.frequencia  = 2 THEN 'F4'
          ELSE 'F5'
        END
    END AS freq_bucket,
    CASE
      WHEN b.recencia_dias <=  30 THEN 'R1'
      WHEN b.recencia_dias <=  60 THEN 'R2'
      WHEN b.recencia_dias <= 120 THEN 'R3'
      WHEN b.recencia_dias <= 180 THEN 'R4'
      ELSE 'R5'
    END AS rec_bucket
  FROM rfv_base b
),

segmentado AS (
  SELECT
    s.*,
    CASE CONCAT(s.freq_bucket, s.rec_bucket)
      WHEN 'F1R1' THEN 'Campeões'
      WHEN 'F1R2' THEN 'Fiéis'         WHEN 'F1R3' THEN 'Fiéis'
      WHEN 'F1R4' THEN 'Não pode perder' WHEN 'F1R5' THEN 'Não pode perder'
      WHEN 'F2R1' THEN 'Fiéis'         WHEN 'F2R2' THEN 'Fiéis'
      WHEN 'F2R3' THEN 'Fiéis'
      WHEN 'F2R4' THEN 'Em risco'      WHEN 'F2R5' THEN 'Em risco'
      WHEN 'F3R1' THEN 'Fiéis em potencial' WHEN 'F3R2' THEN 'Fiéis em potencial'
      WHEN 'F3R3' THEN 'Precisando de atenção'
      WHEN 'F3R4' THEN 'Em risco'      WHEN 'F3R5' THEN 'Em risco'
      WHEN 'F4R1' THEN 'Fiéis em potencial' WHEN 'F4R2' THEN 'Fiéis em potencial'
      WHEN 'F4R3' THEN 'Quase dormentes'
      WHEN 'F4R4' THEN 'Hibernando'    WHEN 'F4R5' THEN 'Perdidos'
      WHEN 'F5R1' THEN 'Novos clientes' WHEN 'F5R2' THEN 'Promessas'
      WHEN 'F5R3' THEN 'Quase dormentes'
      WHEN 'F5R4' THEN 'Perdidos'      WHEN 'F5R5' THEN 'Perdidos'
      ELSE 'Outros'
    END AS segmento,
    CASE CONCAT(s.freq_bucket, s.rec_bucket)
      WHEN 'F1R1' THEN 1
      WHEN 'F1R2' THEN 2 WHEN 'F1R3' THEN 2
      WHEN 'F2R1' THEN 2 WHEN 'F2R2' THEN 2 WHEN 'F2R3' THEN 2
      WHEN 'F3R1' THEN 3 WHEN 'F3R2' THEN 3
      WHEN 'F4R1' THEN 3 WHEN 'F4R2' THEN 3
      WHEN 'F5R1' THEN 4 WHEN 'F5R2' THEN 5
      WHEN 'F3R3' THEN 6
      WHEN 'F4R3' THEN 7 WHEN 'F5R3' THEN 7
      WHEN 'F1R4' THEN 8 WHEN 'F1R5' THEN 8
      WHEN 'F2R4' THEN 9 WHEN 'F2R5' THEN 9
      WHEN 'F3R4' THEN 9 WHEN 'F3R5' THEN 9
      WHEN 'F4R4' THEN 10
      WHEN 'F4R5' THEN 11 WHEN 'F5R4' THEN 11 WHEN 'F5R5' THEN 11
      ELSE 99
    END AS seg_num
  FROM scored s
)

SELECT
  rfv_familia,
  segmento,
  seg_num,
  COUNT(DISTINCT partner_name)  AS clientes,
  ROUND(SUM(valor_total), 2)    AS faturamento
FROM segmentado
GROUP BY rfv_familia, segmento, seg_num
ORDER BY rfv_familia, seg_num
"""

df = client.query(sql).to_dataframe()

# Resultados do Alves (extraídos das planilhas de abril)
ALVES = {
    "HOSPITALAR": {
        "Campeões": (80, 5433495.06), "Fiéis": (47, 913015.92),
        "Fiéis em potencial": (112, 737901.35), "Novos clientes": (38, 90329.29),
        "Promessas": (28, 65556.24), "Precisando de atenção": (6, 34104.56),
        "Quase dormentes": (63, 279801.13), "Não pode perder": (11, 332501.15),
        "Em risco": (21, 152625.23), "Hibernando": (41, 256044.96),
        "Perdidos": (339, 908598.92),
    },
    "FARMACIAS": {
        "Campeões": (0, 0), "Fiéis": (0, 0), "Fiéis em potencial": (0, 0),
        "Novos clientes": (0, 0), "Promessas": (0, 0),
        "Precisando de atenção": (0, 0), "Quase dormentes": (0, 0),
        "Não pode perder": (5, 23895.76), "Em risco": (31, 96340.49),
        "Hibernando": (21, 23562.42), "Perdidos": (191, 231345.42),
    },
    "SAC": {
        "Campeões": (0, 0), "Fiéis": (0, 0),
        "Fiéis em potencial": (1, 630.0), "Novos clientes": (0, 0),
        "Promessas": (3, 612.54), "Precisando de atenção": (0, 0),
        "Quase dormentes": (8, 4664.13), "Não pode perder": (4, 102913.68),
        "Em risco": (4, 26242.02), "Hibernando": (4, 47362.32),
        "Perdidos": (55, 38755.30),
    },
}

SEG_ORDER = [
    "Campeões", "Fiéis", "Fiéis em potencial", "Novos clientes", "Promessas",
    "Precisando de atenção", "Quase dormentes", "Não pode perder",
    "Em risco", "Hibernando", "Perdidos",
]

for familia in ["HOSPITALAR", "FARMACIAS", "SAC"]:
    sub = df[df["rfv_familia"] == familia]
    nosso = {r["segmento"]: (int(r["clientes"]), float(r["faturamento"])) for _, r in sub.iterrows()}
    alves = ALVES[familia]

    total_n_cli = sum(v[0] for v in nosso.values())
    total_n_fat = sum(v[1] for v in nosso.values())
    total_a_cli = sum(v[0] for v in alves.values())
    total_a_fat = sum(v[1] for v in alves.values())

    print(f"\n{'='*72}")
    print(f"  {familia}  |  Janela: {DATA_INI} → {DATA_FIM}  |  Ref: {DATA_REF}")
    print(f"{'='*72}")
    print(f"  {'Segmento':<25} {'Alves':>7} {'Nosso':>7} {'Δ':>5}  {'Fat Alves':>13} {'Fat Nosso':>13}")
    print(f"  {'-'*25} {'-'*7} {'-'*7} {'-'*5}  {'-'*13} {'-'*13}")
    for seg in SEG_ORDER:
        a_cli, a_fat = alves.get(seg, (0, 0))
        n_cli, n_fat = nosso.get(seg, (0, 0))
        delta = n_cli - a_cli
        ok = "✅" if delta == 0 else ("▲" if delta > 0 else "▼")
        print(f"  {seg:<25} {a_cli:>7} {n_cli:>7} {ok}{delta:>+4}  R${a_fat:>11,.0f} R${n_fat:>11,.0f}")
    print(f"  {'─'*25} {'─'*7} {'─'*7} {'─'*5}  {'─'*13} {'─'*13}")
    print(f"  {'TOTAL':<25} {total_a_cli:>7} {total_n_cli:>7} {total_n_cli-total_a_cli:>+5}  R${total_a_fat:>11,.0f} R${total_n_fat:>11,.0f}")
