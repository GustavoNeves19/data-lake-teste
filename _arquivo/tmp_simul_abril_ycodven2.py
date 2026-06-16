"""Simulação Abril/2026 — distribuição por vendedor: CARTEIRA atual vs ERP YCODVEN2 dominante."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

DATA_REF = '2026-04-30'

# --- A) DISTRIBUIÇÃO ATUAL (carteira) --------------------------------
sql_atual = f"""
SELECT
  rfv_familia,
  COALESCE(rfv_salesperson, 'Sem Vendedor') AS vendedor,
  COUNT(DISTINCT partner_name) AS clientes,
  ROUND(SUM(valor_total), 0) AS faturamento
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
WHERE DATE(data_referencia) = '{DATA_REF}'
GROUP BY 1,2
"""
df_atual = c.query(sql_atual).to_dataframe()
df_atual['fonte'] = 'CARTEIRA (atual)'

# --- B) SIMULAÇÃO: vendedor vem do ERP (YCODVEN2 dominante 12 meses) -
sql_sim = f"""
WITH vendas AS (
  SELECT o.partner_code, o.order_number, o.order_date, o.total_amount,
         o.salesperson_name AS vend_erp
  FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
  JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
    ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
  WHERE o.order_status IN (3,4)
    AND o.order_date BETWEEN DATE_SUB(DATE('{DATA_REF}'), INTERVAL 12 MONTH) AND DATE('{DATA_REF}')
),
vendedor_dominante AS (
  SELECT partner_code, vend_erp, qtd,
         ROW_NUMBER() OVER (PARTITION BY partner_code ORDER BY qtd DESC, vend_erp) AS rn
  FROM (
    SELECT partner_code, vend_erp, COUNT(*) AS qtd
    FROM vendas WHERE vend_erp IS NOT NULL
    GROUP BY 1,2
  )
),
base AS (
  SELECT v.partner_code, ca.rfv_familia,
         SUM(v.total_amount) AS faturamento
  FROM vendas v
  JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` ca
    ON ca.partner_code = v.partner_code AND ca.is_active = TRUE
  GROUP BY 1,2
)
SELECT
  b.rfv_familia,
  COALESCE(d.vend_erp, 'Sem Vendedor') AS vendedor,
  COUNT(DISTINCT b.partner_code) AS clientes,
  ROUND(SUM(b.faturamento), 0) AS faturamento
FROM base b
LEFT JOIN vendedor_dominante d ON d.partner_code = b.partner_code AND d.rn = 1
GROUP BY 1, 2
"""
df_sim = c.query(sql_sim).to_dataframe()
df_sim['fonte'] = 'ERP YCODVEN2 (simulação)'

# --- COMPARATIVO --------------------------------------------------
print('=' * 110)
print(f'COMPARATIVO ABRIL/2026 — Distribuicao por Vendedor por Familia')
print(f'Data referencia: {DATA_REF}')
print('=' * 110)

for fam in ['HOSPITALAR', 'FARMACIAS', 'SAC']:
    print(f'\n--- {fam} ---')
    a = df_atual[df_atual['rfv_familia']==fam].sort_values('faturamento', ascending=False)
    s = df_sim[df_sim['rfv_familia']==fam].sort_values('faturamento', ascending=False)

    print(f'\n  ATUAL (carteira): {a["clientes"].sum()} clientes, R$ {a["faturamento"].sum():,.0f}')
    print(a[['vendedor','clientes','faturamento']].to_string(index=False))

    print(f'\n  SIMULACAO (ERP YCODVEN2 dominante): {s["clientes"].sum()} clientes, R$ {s["faturamento"].sum():,.0f}')
    print(s[['vendedor','clientes','faturamento']].to_string(index=False))

print('\n' + '=' * 110)
print('RESUMO DA MUDANCA')
print('=' * 110)
for fam in ['HOSPITALAR', 'FARMACIAS', 'SAC']:
    a = df_atual[df_atual['rfv_familia']==fam]
    s = df_sim[df_sim['rfv_familia']==fam]
    a_vend = set(a['vendedor'])
    s_vend = set(s['vendedor'])
    print(f'\n  {fam}:')
    print(f'    Vendedores na carteira: {sorted(a_vend)}')
    print(f'    Vendedores no ERP:      {sorted(s_vend)}')
    print(f'    NOVOS no ERP:           {sorted(s_vend - a_vend)}')
    print(f'    SAEM da carteira:       {sorted(a_vend - s_vend)}')
