"""
Correlação Hospitalar Abril/2026 — 3 bases:
  1. Planilha Alves (RFV Hospitalar 01-04-2025 até 30-04-2026)
  2. BigQuery — fact_sales_order direto (janela 01/04/2025–30/04/2026)
  3. Notas.xlsx (Maio/2026 — para contexto, NÃO entra na correlação de Abril)

Filtro alinhado com Alves: apenas 3 vendedores (sem Kauan Ramos, sem Eduardo).
"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

import pandas as pd
from google.cloud import bigquery

PROJ = 'sapient-metrics-492914-m7'
REF  = "DATE '2026-04-30'"   # data de referência (igual à janela do Alves)

# Vendedores que entram na correlação (espelha 'Resultado Geral' do Alves)
VENDEDORES_ALVES = ['Guilherme Aquino', 'Kauã Rodrigues', 'Richard Lucas']

# Resultado do Alves (extraído de "Resultado Geral" da planilha)
ALVES_GERAL = {
    'clientes':    786,
    'faturamento': 9_203_973.81,
}
ALVES_VENDEDOR = {
    'Guilherme Aquino': (290, 4_575_536.20),
    'Kauã Rodrigues':   (226, 2_490_144.38),
    'Richard Lucas':    (209,   524_728.62),
}
ALVES_SEGMENTOS = {
    'Campeões':              ( 80, 5_433_495.06),
    'Fiéis':                 ( 47,   913_015.92),
    'Fiéis em potencial':    (112,   737_901.35),
    'Não pode perder':       ( 11,   332_501.15),
    'Em risco':              ( 21,   152_625.23),
    'Hibernando':            ( 41,   256_044.96),
    'Perdidos':              (339,   908_598.92),
    'Precisando de atenção': (  6,    34_104.56),
    'Quase dormentes':       ( 63,   279_801.13),
    'Novos clientes':        ( 38,    90_329.29),
    'Promessas':             ( 28,    65_556.24),
}

client = bigquery.Client(project=PROJ, location='us-east1')


def fmt_brl(v: float) -> str:
    return f"R$ {v:>14,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def query_bq_abril() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (por vendedor, por segmento) — mesma janela do Alves (Abr/2025–Abr/2026)."""
    vendedores_in = ", ".join(f"'{v}'" for v in VENDEDORES_ALVES)
    sql = f"""
    WITH base AS (
        SELECT
            c.partner_name,
            c.salesperson_name AS rfv_salesperson,
            DATE_DIFF({REF}, MAX(o.order_date), DAY)   AS recencia_dias,
            COUNT(DISTINCT o.order_number)              AS frequencia,
            ROUND(SUM(o.total_amount), 2)               AS valor_total
        FROM `{PROJ}.dm_orders.fact_sales_order` o
        JOIN `{PROJ}.silver_comercial.param_com_rfv_carteira` c
            ON  c.partner_code     = o.partner_code
            AND c.is_active        = TRUE
            AND c.salesperson_name IN ({vendedores_in})
        JOIN `{PROJ}.dm_orders.dim_operation_nature` n
            ON  n.nature_code     = o.nature_code
            AND n.financial_flag <> 'N'
        WHERE o.order_status IN (3, 4)
          AND o.order_date >= DATE '2025-04-01'
          AND o.order_date <= DATE '2026-04-30'
        GROUP BY c.partner_name, c.salesperson_name
    ),
    scored AS (
        SELECT
            b.*,
            CASE
                WHEN frequencia >= 5 THEN 'F1'
                WHEN frequencia  = 4 THEN 'F2'
                WHEN frequencia  = 3 THEN 'F3'
                WHEN frequencia  = 2 THEN 'F4'
                ELSE                     'F5'
            END AS freq_bucket,
            CASE
                WHEN recencia_dias <=  30 THEN 'R1'
                WHEN recencia_dias <=  60 THEN 'R2'
                WHEN recencia_dias <= 120 THEN 'R3'
                WHEN recencia_dias <= 180 THEN 'R4'
                ELSE                          'R5'
            END AS rec_bucket
        FROM base b
    ),
    classified AS (
        SELECT
            s.*,
            CASE CONCAT(s.freq_bucket, s.rec_bucket)
                WHEN 'F1R1' THEN 'Campeões'
                WHEN 'F1R2' THEN 'Fiéis'             WHEN 'F1R3' THEN 'Fiéis'
                WHEN 'F1R4' THEN 'Não pode perder'   WHEN 'F1R5' THEN 'Não pode perder'
                WHEN 'F2R1' THEN 'Fiéis'             WHEN 'F2R2' THEN 'Fiéis'
                WHEN 'F2R3' THEN 'Fiéis'
                WHEN 'F2R4' THEN 'Em risco'          WHEN 'F2R5' THEN 'Em risco'
                WHEN 'F3R1' THEN 'Fiéis em potencial' WHEN 'F3R2' THEN 'Fiéis em potencial'
                WHEN 'F3R3' THEN 'Precisando de atenção'
                WHEN 'F3R4' THEN 'Em risco'          WHEN 'F3R5' THEN 'Em risco'
                WHEN 'F4R1' THEN 'Fiéis em potencial' WHEN 'F4R2' THEN 'Fiéis em potencial'
                WHEN 'F4R3' THEN 'Quase dormentes'
                WHEN 'F4R4' THEN 'Hibernando'        WHEN 'F4R5' THEN 'Perdidos'
                WHEN 'F5R1' THEN 'Novos clientes'
                WHEN 'F5R2' THEN 'Promessas'
                WHEN 'F5R3' THEN 'Quase dormentes'
                WHEN 'F5R4' THEN 'Perdidos'          WHEN 'F5R5' THEN 'Perdidos'
                ELSE 'Outros'
            END AS segmento
        FROM scored s
    )
    SELECT
        rfv_salesperson, segmento,
        COUNT(DISTINCT partner_name)    AS clientes,
        ROUND(SUM(valor_total), 2)      AS faturamento
    FROM classified
    GROUP BY 1, 2
    """
    df = client.query(sql).to_dataframe()

    por_vendedor = (df.groupby('rfv_salesperson')
                      .agg(clientes=('clientes','sum'), faturamento=('faturamento','sum'))
                      .reset_index())
    por_segmento = (df.groupby('segmento')
                      .agg(clientes=('clientes','sum'), faturamento=('faturamento','sum'))
                      .reset_index())
    return por_vendedor, por_segmento


def query_notas_maio() -> tuple[int, float]:
    """Total de NF em Maio/2026 (apenas para contexto)."""
    f = r'C:\Users\gusta\Downloads\Notas.xlsx'
    df = pd.read_excel(f)
    return len(df), float(df['yvaltot'].sum())


def print_sep(c='='):
    print(c * 110)


def main():
    print_sep()
    print("  CORRELAÇÃO HOSPITALAR ABRIL/2026 — Alves vs BigQuery (mesma janela e 3 vendedores)")
    print_sep()
    print(f"  Janela: 01/04/2025 → 30/04/2026")
    print(f"  Vendedores: {', '.join(VENDEDORES_ALVES)}")

    bq_vend, bq_seg = query_bq_abril()
    bq_dict_vend = {r['rfv_salesperson']: (int(r['clientes']), float(r['faturamento']))
                    for _, r in bq_vend.iterrows()}
    bq_total_cli = int(bq_vend['clientes'].sum())
    bq_total_fat = float(bq_vend['faturamento'].sum())

    print()
    print("  POR VENDEDOR")
    print('-' * 110)
    print(f"  {'Vendedor':<22} {'Alves Cli':>10} {'BQ Cli':>8} {'Δ Cli':>7}   "
          f"{'Alves Fat':>18} {'BQ Fat':>18} {'Δ Fat %':>9}")
    print('-' * 110)
    for v in VENDEDORES_ALVES:
        a_cli, a_fat = ALVES_VENDEDOR[v]
        b_cli, b_fat = bq_dict_vend.get(v, (0, 0.0))
        d_cli = b_cli - a_cli
        d_fat_pct = (b_fat - a_fat) / a_fat * 100 if a_fat else 0
        print(f"  {v:<22} {a_cli:>10} {b_cli:>8} {d_cli:>+7}   "
              f"{fmt_brl(a_fat):>18} {fmt_brl(b_fat):>18} {d_fat_pct:>+8.1f}%")
    print('-' * 110)
    d_cli = bq_total_cli - ALVES_GERAL['clientes']
    d_fat_pct = (bq_total_fat - ALVES_GERAL['faturamento']) / ALVES_GERAL['faturamento'] * 100
    print(f"  {'TOTAL':<22} {ALVES_GERAL['clientes']:>10} {bq_total_cli:>8} {d_cli:>+7}   "
          f"{fmt_brl(ALVES_GERAL['faturamento']):>18} {fmt_brl(bq_total_fat):>18} {d_fat_pct:>+8.1f}%")

    print()
    print("  POR SEGMENTO")
    print('-' * 110)
    bq_dict_seg = {r['segmento']: (int(r['clientes']), float(r['faturamento']))
                   for _, r in bq_seg.iterrows()}
    print(f"  {'Segmento':<26} {'Alves Cli':>10} {'BQ Cli':>8} {'Δ Cli':>7}   "
          f"{'Alves Fat':>18} {'BQ Fat':>18} {'Δ Fat %':>9}")
    print('-' * 110)
    ordem = ['Campeões', 'Fiéis', 'Fiéis em potencial', 'Não pode perder',
             'Em risco', 'Hibernando', 'Perdidos', 'Precisando de atenção',
             'Quase dormentes', 'Novos clientes', 'Promessas']
    for seg in ordem:
        a_cli, a_fat = ALVES_SEGMENTOS.get(seg, (0, 0.0))
        b_cli, b_fat = bq_dict_seg.get(seg, (0, 0.0))
        d_cli = b_cli - a_cli
        d_fat_pct = (b_fat - a_fat) / a_fat * 100 if a_fat else 0
        print(f"  {seg:<26} {a_cli:>10} {b_cli:>8} {d_cli:>+7}   "
              f"{fmt_brl(a_fat):>18} {fmt_brl(b_fat):>18} {d_fat_pct:>+8.1f}%")

    print()
    print_sep()
    print("  CONTEXTO — Notas.xlsx (NÃO entra na correlação de Abril)")
    print_sep()
    n_qtd, n_fat = query_notas_maio()
    print(f"  Notas.xlsx contém {n_qtd} NF de 01/05/2026 a 25/05/2026 ({fmt_brl(n_fat)}).")
    print("  Composição majoritariamente CONSUMIDOR FINAL (e-commerce), não Hospitalar B2B.")
    print("  Para comparativo Abril seria necessário um relatório de NF do mesmo período (01/04/25–30/04/26).")
    print_sep()


if __name__ == '__main__':
    main()
