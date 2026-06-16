"""
Diagnóstico das naturezas usadas no HOSPITALAR — janela RFV de abril/2026.
Mostra cada nature_code com:
  - financial_flag (N = excluído pelo nosso filtro hoje)
  - clientes distintos, total faturado, qtd pedidos
Para identificar se naturezas de substituição/troca explicam o gap de R$ 1,375M.
"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

from google.cloud import bigquery

PROJ = 'sapient-metrics-492914-m7'
client = bigquery.Client(project=PROJ, location='us-east1')

SQL = f"""
SELECT
    o.nature_code,
    n.nature_name,
    n.financial_flag,
    n.is_return,
    n.direction,
    COUNT(DISTINCT o.partner_code)              AS clientes,
    COUNT(DISTINCT o.order_number)              AS pedidos,
    ROUND(SUM(o.total_amount), 2)               AS faturamento
FROM `{PROJ}.dm_orders.fact_sales_order` o
JOIN `{PROJ}.silver_comercial.param_com_rfv_carteira` c
    ON  c.partner_code = o.partner_code
    AND c.is_active    = TRUE
    AND c.rfv_familia  = 'HOSPITALAR'
LEFT JOIN `{PROJ}.dm_orders.dim_operation_nature` n
    ON n.nature_code = o.nature_code
WHERE o.order_status IN (3, 4)
  AND o.order_date >= DATE '2025-04-01'
  AND o.order_date <= DATE '2026-04-30'
GROUP BY o.nature_code, n.nature_name, n.financial_flag, n.is_return, n.direction
ORDER BY faturamento DESC NULLS LAST
"""

def fmt(v):
    if v is None: return ''
    return f"R$ {v:>14,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

df = client.query(SQL).to_dataframe()
print('=' * 130)
print('  HOSPITALAR — Naturezas usadas em 01/04/2025 → 30/04/2026 (carteira ativa)')
print('=' * 130)
print(f"  {'Cod':<6} {'Flag':<5} {'Ret':<4} {'Dir':<4} {'Nome':<48} {'Cli':>5} {'Ped':>6} {'Faturamento':>20}")
print('-' * 130)

tot_n = tot_ok = 0.0
n_codes_n, n_codes_ok = [], []
for _, r in df.iterrows():
    flag = r['financial_flag'] or '?'
    ret  = r['is_return'] or ''
    dir_ = r['direction'] or ''
    desc = (r['nature_name'] or '')[:46]
    fat  = float(r['faturamento']) if r['faturamento'] else 0
    print(f"  {r['nature_code']:<6} {flag:<5} {ret:<4} {dir_:<4} {desc:<48} {int(r['clientes']):>5} {int(r['pedidos']):>6} {fmt(fat):>20}")
    if flag == 'N':
        tot_n += fat
        n_codes_n.append((r['nature_code'], desc, fat))
    else:
        tot_ok += fat
        n_codes_ok.append((r['nature_code'], desc, fat))

print('-' * 130)
print(f"  Total com financial_flag <> N  (entra hoje):  {fmt(tot_ok)}")
print(f"  Total com financial_flag  = N  (excluído):    {fmt(tot_n)}")
print(f"  Soma geral:                                   {fmt(tot_ok + tot_n)}")
print()
print(f"  Gap vs Alves (R$ 9.203.973,81): {fmt(9_203_973.81 - tot_ok)}")
print(f"  Naturezas N somam:               {fmt(tot_n)}")
print(f"  Se incluirmos TODAS naturezas:   {fmt(tot_ok + tot_n)}  vs Alves {fmt(9_203_973.81)}")
