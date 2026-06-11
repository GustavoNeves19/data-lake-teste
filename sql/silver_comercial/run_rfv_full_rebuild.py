"""
Rebuild completo do RFV com múltiplos períodos históricos fechados.

Execução: py -3 sql/silver_comercial/run_rfv_full_rebuild.py

Ordem:
  1. Limpa todos os períodos existentes nas tabelas rfv
  2. INSERT INTO para cada mês em PERIODOS_HISTORICOS (meses fechados)
  3. run_gold_comercial.py → gold com todos os períodos

NOTA: o mês atual (em andamento) NÃO é incluído — dados incompletos distorcem
a análise. Quando o mês fechar, adicionar a data em PERIODOS_HISTORICOS.

Para adicionar um novo mês: incluir em PERIODOS_HISTORICOS e rodar o script.
"""
import io, os, sys, subprocess, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\teste\sapient-metrics.json'
from google.cloud import bigquery

PROJ     = 'sapient-metrics-492914-m7'
LOCATION = 'us-east1'
HERE     = os.path.dirname(os.path.abspath(__file__))
ROOT     = os.path.abspath(os.path.join(HERE, '..', '..'))

client = bigquery.Client(project=PROJ, location=LOCATION)

# ── Meses históricos a inserir (último dia de cada mês) ──────────────────────
# O mês atual (CURRENT_DATE) é gerado pelo run_silver_comercial.py.
# Adicione novas datas aqui conforme o dashboard avança.
PERIODOS_HISTORICOS = [
    ("Janeiro/2026",   "DATE '2026-01-31'"),
    ("Fevereiro/2026", "DATE '2026-02-28'"),
    ("Março/2026",     "DATE '2026-03-31'"),
    ("Abril/2026",     "DATE '2026-04-30'"),
    ("Maio/2026",      "DATE '2026-05-31'"),   # fechado — após Diego/Fred subirem NSR_ERP até 31/05
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_bq(label: str, sql: str) -> None:
    print(f"  [{label}]", end=' ', flush=True)
    t0 = time.time()
    job = client.query(sql)
    job.result()
    dt = round(time.time() - t0, 1)
    info = f"{dt}s"
    if job.num_dml_affected_rows is not None:
        info += f" | {job.num_dml_affected_rows} linhas"
    print(f"OK  {info}")


def run_script(path: str) -> None:
    result = subprocess.run([sys.executable, path], capture_output=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Script falhou: {path}")


def insert_periodo(label: str, ref: str) -> None:
    """Insere rfv_base + rfv_score + rfv_resumo para um período histórico."""

    # rfv_base — agrega pedidos com hierarquia de match na carteira (decisão Gustavo 31/05):
    #   1º) cliente em carteira VÁLIDA (4 Hosp + Farm + SAC) → vai pro titular
    #   2º) cliente em carteira COM Eduardo/Karina (licitação/distribuidor) → entra na família
    #       original (HOSPITALAR/FARMACIAS) com salesperson=titular real, pra fechar RFV Geral
    #   3º) cliente SEM carteira nenhuma → vira "NOVOS_CLIENTES"
    #
    # Resultado: TOTAL silver = TOTAL universo ERP (R$ 10,22M em abr/26).
    # No dashboard, ao mostrar "4 carteiras Hospitalar A/B/C/D", filtra-se pelos 4 nomes
    # canônicos (Aquino/Kauã/Richard/Kauan Ramos), deixando Eduardo de fora visualmente.
    # REGRA OFICIAL v5 (decisão 03/06/2026 — match HÍBRIDO partner_code OR nome):
    # 1º: tenta match por partner_code (mais confiável, sem problema de encoding)
    # 2º: fallback por NOME normalizado (cobre filiais não cadastradas no partner_code)
    # 3º: fallback NOVOS_<grupo> pra não-carteirizados
    # Resolve o caso "Paulo Inácio" (R$ 342 SAC) onde encoding inconsistente entre
    # dim_partner e param_com_rfv_carteira fazia match por nome falhar.
    run_bq(f"{label} — rfv_base", f"""
        INSERT INTO `{PROJ}.silver_comercial.silver_com_rfv_base`
        WITH
        carteira_por_codigo AS (
            -- BLINDAGEM contra fan-out: se o mesmo partner_code estiver carteirizado
            -- em 2+ famílias (ex: MED4 em FARMACIAS e HOSPITALAR), o JOIN multiplicaria
            -- a venda e contaria em dobro no GERAL. QUALIFY garante 1 família por código
            -- (determinístico, ordem alfabética da família). Conflitos são reportados
            -- à parte para limpeza manual da carteira.
            SELECT partner_code, partner_name, rfv_familia, salesperson_name
            FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
            WHERE is_active = TRUE
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY partner_code ORDER BY rfv_familia, salesperson_name
            ) = 1
        ),
        carteira_por_nome AS (
            SELECT
                UPPER(REGEXP_REPLACE(
                    NORMALIZE(partner_name, NFD),
                    r'[^A-Za-z0-9 ]', ''
                ))                                                AS nome_norm,
                ANY_VALUE(rfv_familia)       AS rfv_familia,
                ANY_VALUE(salesperson_name)  AS salesperson_name
            FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
            WHERE is_active = TRUE
            GROUP BY 1
            HAVING nome_norm <> ''
        ),
        vendas AS (
            SELECT
                o.*,
                p.partner_name                                    AS partner_name_erp,
                UPPER(REGEXP_REPLACE(
                    NORMALIZE(COALESCE(p.partner_name, ''), NFD),
                    r'[^A-Za-z0-9 ]', ''
                ))                                                AS nome_norm
            FROM `{PROJ}.dm_orders.fact_sales_order` o
            LEFT JOIN `{PROJ}.dm_partners.dim_partner` p
                ON p.partner_code = o.partner_code
        )
        SELECT
            COALESCE(v.partner_name_erp, CAST(v.partner_code AS STRING))            AS partner_name,
            COALESCE(
                cc.rfv_familia,                                  -- 1º match: partner_code (sem encoding)
                cn.rfv_familia,                                  -- 2º match: nome normalizado
                CASE v.salesperson_group_code                    -- 3º fallback: NOVOS_<grupo>
                    WHEN 'FA' THEN 'NOVOS_HOSPITALAR'
                    WHEN 'FR' THEN 'NOVOS_FARMACIAS'
                    WHEN 'PC' THEN 'NOVOS_SAC'
                END
            )                                                                       AS rfv_familia,
            -- Vendedor: titular da carteira (limpo) quando carteirizado; senão
            -- 'Novos Clientes' (decisão 28/05 + 05/06) — NÃO usa o nome bruto do
            -- vendedor-da-venda, pra esses clientes ficarem agrupados num bucket
            -- único pro Alves/Vini redimensionarem (atribuir a uma carteira).
            COALESCE(cc.salesperson_name, cn.salesperson_name,
                     'Novos Clientes')                                              AS rfv_salesperson,
            STRING_AGG(DISTINCT CAST(v.partner_code AS STRING)
                       ORDER BY CAST(v.partner_code AS STRING))                     AS partner_codes_list,
            MAX(v.invoice_date)                                                     AS ultima_compra_data,
            DATE_DIFF({ref}, MAX(v.invoice_date), DAY)                             AS recencia_dias,
            ROUND(DATE_DIFF({ref}, MAX(v.invoice_date), DAY) / 30.0, 6)           AS recencia_meses,
            COUNT(DISTINCT v.order_number)                                          AS frequencia,
            ROUND(SUM(v.product_amount), 2)                                         AS valor_total,
            {ref}                                                                   AS data_referencia
        FROM vendas v
        LEFT JOIN carteira_por_codigo cc ON cc.partner_code = v.partner_code
        LEFT JOIN carteira_por_nome   cn ON cn.nome_norm = v.nome_norm
        JOIN `{PROJ}.dm_orders.dim_operation_nature` n
            ON  n.nature_code     = v.nature_code
            AND n.financial_flag <> 'N'
        WHERE v.order_status IN (3, 4)
          AND v.invoice_date >= DATE_TRUNC(DATE_SUB({ref}, INTERVAL 1 YEAR), MONTH)
          AND v.invoice_date <= {ref}
          AND v.channel_code <> '000054'
          AND (
              cc.partner_code IS NOT NULL                            -- carteirizado por cod
              OR cn.nome_norm IS NOT NULL                            -- carteirizado por nome
              OR v.salesperson_group_code IN ('FA','FR','PC')        -- não cart: só 3 grupos
          )
        GROUP BY
            COALESCE(v.partner_name_erp, CAST(v.partner_code AS STRING)),
            COALESCE(
                cc.rfv_familia,
                cn.rfv_familia,
                CASE v.salesperson_group_code
                    WHEN 'FA' THEN 'NOVOS_HOSPITALAR'
                    WHEN 'FR' THEN 'NOVOS_FARMACIAS'
                    WHEN 'PC' THEN 'NOVOS_SAC'
                END
            ),
            COALESCE(cc.salesperson_name, cn.salesperson_name,
                     'Novos Clientes')
    """)

    # rfv_score — aplica buckets F/R e segmentos
    run_bq(f"{label} — rfv_score", f"""
        INSERT INTO `{PROJ}.silver_comercial.silver_com_rfv_score`
        WITH scored AS (
            SELECT
                b.*,
                CASE
                    WHEN b.rfv_familia IN ('HOSPITALAR', 'SAC',
                                            'NOVOS_HOSPITALAR', 'NOVOS_SAC') THEN
                        CASE
                            WHEN b.frequencia >= 5 THEN 'F1'
                            WHEN b.frequencia  = 4 THEN 'F2'
                            WHEN b.frequencia  = 3 THEN 'F3'
                            WHEN b.frequencia  = 2 THEN 'F4'
                            ELSE                        'F5'
                        END
                    ELSE  -- FARMACIAS / NOVOS_FARMACIAS
                        CASE
                            WHEN b.frequencia >= 7 THEN 'F1'
                            WHEN b.frequencia >= 5 THEN 'F2'
                            WHEN b.frequencia >= 3 THEN 'F3'
                            WHEN b.frequencia  = 2 THEN 'F4'
                            ELSE                        'F5'
                        END
                END AS freq_bucket,
                CASE
                    WHEN b.recencia_dias <=  30 THEN 'R1'
                    WHEN b.recencia_dias <=  60 THEN 'R2'
                    WHEN b.recencia_dias <= 120 THEN 'R3'
                    WHEN b.recencia_dias <= 180 THEN 'R4'
                    ELSE                              'R5'
                END AS rec_bucket
            FROM `{PROJ}.silver_comercial.silver_com_rfv_base` b
            WHERE b.data_referencia = {ref}
        )
        SELECT
            s.*,
            CONCAT(s.freq_bucket, s.rec_bucket) AS classificacao_1,
            CASE CONCAT(s.freq_bucket, s.rec_bucket)
                WHEN 'F1R1' THEN 'Campeões'
                WHEN 'F1R2' THEN 'Fiéis'            WHEN 'F1R3' THEN 'Fiéis'
                WHEN 'F1R4' THEN 'Não pode perder'  WHEN 'F1R5' THEN 'Não pode perder'
                WHEN 'F2R1' THEN 'Fiéis'            WHEN 'F2R2' THEN 'Fiéis'
                WHEN 'F2R3' THEN 'Fiéis'
                WHEN 'F2R4' THEN 'Em risco'         WHEN 'F2R5' THEN 'Em risco'
                WHEN 'F3R1' THEN 'Fiéis em potencial' WHEN 'F3R2' THEN 'Fiéis em potencial'
                WHEN 'F3R3' THEN 'Precisando de atenção'
                WHEN 'F3R4' THEN 'Em risco'         WHEN 'F3R5' THEN 'Em risco'
                WHEN 'F4R1' THEN 'Fiéis em potencial' WHEN 'F4R2' THEN 'Fiéis em potencial'
                WHEN 'F4R3' THEN 'Quase dormentes'
                WHEN 'F4R4' THEN 'Hibernando'       WHEN 'F4R5' THEN 'Perdidos'
                WHEN 'F5R1' THEN 'Novos clientes'
                WHEN 'F5R2' THEN 'Promessas'
                WHEN 'F5R3' THEN 'Quase dormentes'
                WHEN 'F5R4' THEN 'Perdidos'         WHEN 'F5R5' THEN 'Perdidos'
                ELSE 'Outros'
            END AS classificacao_2,
            CASE CONCAT(s.freq_bucket, s.rec_bucket)
                WHEN 'F1R1' THEN 1
                WHEN 'F1R2' THEN 2  WHEN 'F1R3' THEN 2
                WHEN 'F2R1' THEN 2  WHEN 'F2R2' THEN 2  WHEN 'F2R3' THEN 2
                WHEN 'F3R1' THEN 3  WHEN 'F3R2' THEN 3
                WHEN 'F4R1' THEN 3  WHEN 'F4R2' THEN 3
                WHEN 'F5R1' THEN 4
                WHEN 'F5R2' THEN 5
                WHEN 'F3R3' THEN 6
                WHEN 'F4R3' THEN 7  WHEN 'F5R3' THEN 7
                WHEN 'F1R4' THEN 8  WHEN 'F1R5' THEN 8
                WHEN 'F2R4' THEN 9  WHEN 'F2R5' THEN 9
                WHEN 'F3R4' THEN 9  WHEN 'F3R5' THEN 9
                WHEN 'F4R4' THEN 10
                WHEN 'F4R5' THEN 11 WHEN 'F5R4' THEN 11 WHEN 'F5R5' THEN 11
                ELSE 99
            END AS classificacao_3
        FROM scored s
    """)

    # rfv_resumo — sumário por família × vendedor × segmento
    run_bq(f"{label} — rfv_resumo", f"""
        INSERT INTO `{PROJ}.silver_comercial.silver_com_rfv_resumo`
        SELECT
            rfv_familia,
            rfv_salesperson,
            classificacao_2                 AS segmento,
            classificacao_3                 AS segmento_num,
            COUNT(DISTINCT partner_name)    AS qtd_clientes,
            ROUND(SUM(valor_total), 2)      AS faturamento_total,
            ROUND(AVG(valor_total), 2)      AS ticket_medio,
            ROUND(AVG(frequencia), 2)       AS frequencia_media,
            ROUND(AVG(recencia_dias), 1)    AS recencia_media_dias,
            {ref}                           AS data_referencia
        FROM `{PROJ}.silver_comercial.silver_com_rfv_score`
        WHERE data_referencia = {ref}
        GROUP BY rfv_familia, rfv_salesperson, classificacao_2, classificacao_3
        ORDER BY rfv_familia, rfv_salesperson, classificacao_3
    """)


# ──────────────────────────────────────────────────────────────────────────────
# PASSO 1 — Limpa períodos existentes (evita duplicatas em re-runs)
# ──────────────────────────────────────────────────────────────────────────────
print()
print('=' * 70)
print('  PASSO 1/3 — Limpeza das tabelas rfv')
print('=' * 70)
for tbl in ['silver_com_rfv_base', 'silver_com_rfv_score', 'silver_com_rfv_resumo']:
    run_bq(f"DELETE {tbl}", f"DELETE FROM `{PROJ}.silver_comercial.{tbl}` WHERE TRUE")


# ──────────────────────────────────────────────────────────────────────────────
# PASSO 2 — INSERT períodos históricos (meses fechados)
# ──────────────────────────────────────────────────────────────────────────────
print()
print('=' * 70)
print(f'  PASSO 2/3 — INSERT {len(PERIODOS_HISTORICOS)} meses históricos')
print('=' * 70)

for label, ref in PERIODOS_HISTORICOS:
    print(f'\n  >> {label}  ({ref})')
    insert_periodo(label, ref)

# Verificação rápida
print()
print('  Períodos disponíveis em silver_com_rfv_score:')
df = client.query(f"""
    SELECT DATE(data_referencia) AS periodo, COUNT(*) AS clientes
    FROM `{PROJ}.silver_comercial.silver_com_rfv_score`
    GROUP BY 1 ORDER BY 1 DESC
""").to_dataframe()
for _, r in df.iterrows():
    print(f"    {r['periodo']}  →  {int(r['clientes'])} clientes")


# ──────────────────────────────────────────────────────────────────────────────
# PASSO 3 — Gold comercial
# ──────────────────────────────────────────────────────────────────────────────
print()
print('=' * 70)
print('  PASSO 3/3 — Gold comercial')
print('=' * 70)
run_script(os.path.join(ROOT, 'sql', 'gold_comercial', 'run_gold_comercial.py'))

print()
print('=' * 70)
print('  REBUILD COMPLETO ✓')
periodos_str = ' + '.join(l for l, _ in PERIODOS_HISTORICOS)
print(f'  Silver: {periodos_str}')
print('  Gold:   gold_com_cliente_360, gold_com_alerta_comercial,')
print('          gold_com_vendedor_painel, gold_com_pipeline_crm')
print('=' * 70)
