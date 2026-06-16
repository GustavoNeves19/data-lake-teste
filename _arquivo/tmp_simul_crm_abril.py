"""Simulação Abril/2026 — RFV usando vendedor do CRM owner vs carteira atual."""
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

# --- A) ATUAL: silver_com_rfv_score já calculado para 2026-04-30 ----
sql_atual = f"""
SELECT
  rfv_familia,
  COALESCE(rfv_salesperson, 'Sem Vendedor') AS vendedor,
  COUNT(DISTINCT partner_name) AS clientes,
  ROUND(SUM(valor_total), 0) AS faturamento
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
WHERE DATE(data_referencia) = '{DATA_REF}'
GROUP BY 1, 2
"""
df_atual = c.query(sql_atual).to_dataframe()

# --- B) SIMULADO: mesmo perimetro mas vendedor = CRM owner ----------
# Refaz o calculo de RFV usando carteira (rfv_familia) + vendedor vindo do CRM
sql_sim = f"""
WITH vendas AS (
  SELECT
    o.partner_code,
    o.order_number,
    o.order_date,
    o.total_amount
  FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
  JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` ca
    ON ca.partner_code = o.partner_code AND ca.is_active = TRUE
  JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
    ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
  WHERE o.order_status IN (3, 4)
    AND o.order_date BETWEEN DATE_SUB(DATE('{DATA_REF}'), INTERVAL 12 MONTH) AND DATE('{DATA_REF}')
),
crm_owner AS (
  SELECT b.partner_code, u.name AS vend_crm
  FROM `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge` b
  JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_organization` o ON o.org_id = b.org_id
  LEFT JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_user` u ON u.user_id = o.owner_id
  WHERE b.is_active = TRUE
),
base AS (
  SELECT
    v.partner_code,
    ca.partner_name,
    ca.rfv_familia,
    COALESCE(cr.vend_crm, 'Sem Vendedor (sem CRM)') AS vendedor_crm,
    SUM(v.total_amount) AS valor_total,
    COUNT(DISTINCT v.order_number) AS frequencia,
    DATE_DIFF(DATE('{DATA_REF}'), MAX(v.order_date), DAY) AS recencia_dias
  FROM vendas v
  JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` ca
    ON ca.partner_code = v.partner_code AND ca.is_active = TRUE
  LEFT JOIN crm_owner cr ON cr.partner_code = v.partner_code
  GROUP BY 1, 2, 3, 4
)
SELECT
  rfv_familia,
  vendedor_crm AS vendedor,
  COUNT(DISTINCT partner_code) AS clientes,
  ROUND(SUM(valor_total), 0) AS faturamento,
  ROUND(AVG(recencia_dias), 0) AS rec_media_dias
FROM base
GROUP BY 1, 2
"""
df_sim = c.query(sql_sim).to_dataframe()

# --- COMPARATIVO ---------------------------------------------------
print('=' * 110)
print(f'SIMULAÇÃO ABRIL/2026 — Carteira ATUAL (planilha+manual) vs CRM owner (proposto)')
print(f'Data referência: {DATA_REF} | Mesmo período RFV (12 meses)')
print('=' * 110)

for fam in ['HOSPITALAR', 'FARMACIAS', 'SAC']:
    print(f'\n{"="*70}')
    print(f'  {fam}')
    print('=' * 70)
    a = df_atual[df_atual['rfv_familia']==fam].sort_values('faturamento', ascending=False).reset_index(drop=True)
    s = df_sim[df_sim['rfv_familia']==fam].sort_values('faturamento', ascending=False).reset_index(drop=True)

    print(f'\n  ATUAL (carteira manual): {int(a["clientes"].sum())} cli / R$ {a["faturamento"].sum():,.0f}')
    print('  ' + '─' * 60)
    print(a[['vendedor','clientes','faturamento']].to_string(index=False))

    print(f'\n  SIMULADO (vendedor=CRM owner): {int(s["clientes"].sum())} cli / R$ {s["faturamento"].sum():,.0f}')
    print('  ' + '─' * 60)
    print(s[['vendedor','clientes','faturamento','rec_media_dias']].to_string(index=False))

# Total geral
print('\n' + '=' * 110)
print('TOTAL GERAL')
print('=' * 110)
print(f'  ATUAL:    {int(df_atual["clientes"].sum())} cli / R$ {df_atual["faturamento"].sum():,.0f}')
print(f'  SIMULADO: {int(df_sim["clientes"].sum())} cli / R$ {df_sim["faturamento"].sum():,.0f}')
print(f'  Delta:    {int(df_sim["clientes"].sum()) - int(df_atual["clientes"].sum()):+d} cli / R$ {df_sim["faturamento"].sum() - df_atual["faturamento"].sum():+,.0f}')

# Quem some, quem aparece
print('\n=== VENDEDORES — diferença entre fontes ===')
for fam in ['HOSPITALAR', 'FARMACIAS', 'SAC']:
    print(f'\n  {fam}:')
    a = set(df_atual[df_atual['rfv_familia']==fam]['vendedor'].dropna())
    s = set(df_sim[df_sim['rfv_familia']==fam]['vendedor'].dropna())
    print(f'    Some do RFV (estava só na carteira): {sorted(a - s)}')
    print(f'    Aparece (estava só no CRM):          {sorted(s - a)}')
    print(f'    Comum (ambos):                       {sorted(a & s)}')
