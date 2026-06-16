"""
Simulação Abril/2026 — comparativo BQ vs planilha Alves, 3 canais.
Janela: 01/04/2025 → 30/04/2026 (mesma do snapshot RFV de abril).
Filtro natureza: financial_flag <> 'N' (códigos que geram faturamento).
Classificação de canal: rfv_familia da carteira (HOSPITALAR/SAC/FARMACIAS).
"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

from google.cloud import bigquery

PROJ = 'sapient-metrics-492914-m7'
client = bigquery.Client(project=PROJ, location='us-east1')

ALVES = {
    'HOSPITALAR': (786, 9_203_973.81),
    'SAC':        ( 79,   221_179.99),
    'FARMACIAS':  (248,   375_144.09),
}

SQL = f"""
WITH base AS (
    SELECT
        c.rfv_familia,
        c.partner_name,
        SUM(o.total_amount) AS valor
    FROM `{PROJ}.dm_orders.fact_sales_order` o
    JOIN `{PROJ}.silver_comercial.param_com_rfv_carteira` c
        ON  c.partner_code = o.partner_code
        AND c.is_active    = TRUE
    JOIN `{PROJ}.dm_orders.dim_operation_nature` n
        ON  n.nature_code     = o.nature_code
        AND n.financial_flag <> 'N'
    WHERE o.order_status IN (3, 4)
      AND o.order_date >= DATE '2025-04-01'
      AND o.order_date <= DATE '2026-04-30'
    GROUP BY c.rfv_familia, c.partner_name
)
SELECT
    rfv_familia,
    COUNT(DISTINCT partner_name) AS clientes,
    ROUND(SUM(valor), 2)         AS faturamento
FROM base
GROUP BY rfv_familia
ORDER BY rfv_familia
"""

def fmt(v): return f"R$ {v:>16,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

df = client.query(SQL).to_dataframe()
bq = {r['rfv_familia']: (int(r['clientes']), float(r['faturamento'])) for _, r in df.iterrows()}

print('=' * 110)
print('  SIMULAÇÃO ABRIL/2026 — BigQuery vs Planilha Alves (janela 01/04/25 → 30/04/26)')
print('=' * 110)
print(f"  {'Canal':<12} | {'Alves Cli':>10} {'BQ Cli':>8} {'Δ Cli':>7} | "
      f"{'Alves Fat':>20} {'BQ Fat':>20} {'Δ R$':>15} {'Δ %':>7}")
print('-' * 110)

tot_a_cli = tot_a_fat = tot_b_cli = tot_b_fat = 0
for canal in ['HOSPITALAR', 'SAC', 'FARMACIAS']:
    a_cli, a_fat = ALVES[canal]
    b_cli, b_fat = bq.get(canal, (0, 0.0))
    d_cli = b_cli - a_cli
    d_fat = b_fat - a_fat
    d_pct = (d_fat / a_fat * 100) if a_fat else 0
    print(f"  {canal:<12} | {a_cli:>10} {b_cli:>8} {d_cli:>+7} | "
          f"{fmt(a_fat):>20} {fmt(b_fat):>20} {fmt(d_fat):>15} {d_pct:>+6.1f}%")
    tot_a_cli += a_cli; tot_a_fat += a_fat
    tot_b_cli += b_cli; tot_b_fat += b_fat

print('-' * 110)
d_cli = tot_b_cli - tot_a_cli
d_fat = tot_b_fat - tot_a_fat
d_pct = (d_fat / tot_a_fat * 100) if tot_a_fat else 0
print(f"  {'TOTAL':<12} | {tot_a_cli:>10} {tot_b_cli:>8} {d_cli:>+7} | "
      f"{fmt(tot_a_fat):>20} {fmt(tot_b_fat):>20} {fmt(d_fat):>15} {d_pct:>+6.1f}%")
print('=' * 110)

# Detalhe extra: outros rfv_familia que apareceram no BQ
outros = [k for k in bq if k not in ALVES]
if outros:
    print()
    print('  Outras famílias presentes no BQ (fora da comparação):')
    for k in outros:
        c, f = bq[k]
        print(f'    {k}: {c} clientes / {fmt(f)}')
