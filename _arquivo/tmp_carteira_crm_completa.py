"""Carteira via CRM owner — confronto com ERP YCODVEN2 e carteira manual."""
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

# Schema bridge
print('=== Schema param_com_entity_bridge ===')
try:
    t = c.get_table('sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge')
    for f in t.schema:
        print(f'  {f.name} {f.field_type}')
    print(f'  total: {t.num_rows} linhas')
except Exception as e:
    print(f'  ERRO: {e}')

# Amostra bridge
print('\n=== Amostra bridge ===')
br = c.query("""
SELECT *
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge`
LIMIT 5
""").to_dataframe()
print(br.to_string(index=False))

# Cobertura: quantos partner_code da carteira tem org_id no CRM?
print('\n=== Cobertura: carteira × CRM ===')
cob = c.query("""
WITH ca AS (
  SELECT partner_code, partner_name, rfv_familia, salesperson_name
  FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
  WHERE is_active = TRUE
)
SELECT
  ca.rfv_familia,
  COUNT(DISTINCT ca.partner_code) AS clientes_carteira,
  COUNT(DISTINCT CASE WHEN b.org_id IS NOT NULL THEN ca.partner_code END) AS com_crm,
  COUNT(DISTINCT CASE WHEN b.org_id IS NULL THEN ca.partner_code END) AS sem_crm
FROM ca
LEFT JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge` b
  ON b.partner_code = ca.partner_code
GROUP BY 1 ORDER BY 1
""").to_dataframe()
print(cob.to_string(index=False))

# Comparativo das 3 fontes: planilha/carteira × ERP × CRM
print('\n=== Para cada cliente: vendedor carteira × vendedor ERP × vendedor CRM ===')
trip = c.query("""
WITH erp_dom AS (
  SELECT partner_code, salesperson_name AS vend_erp,
         ROW_NUMBER() OVER (PARTITION BY partner_code ORDER BY COUNT(*) DESC) AS rn
  FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
  WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    AND order_status IN (3,4) AND salesperson_name IS NOT NULL
  GROUP BY 1, 2
),
crm_owner AS (
  SELECT b.partner_code, u.name AS vend_crm
  FROM `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge` b
  JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_organization` o ON o.org_id = b.org_id
  LEFT JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_user` u ON u.user_id = o.owner_id
)
SELECT
  ca.partner_code,
  ca.partner_name,
  ca.rfv_familia,
  ca.salesperson_name AS vend_carteira,
  e.vend_erp,
  cr.vend_crm,
  CASE
    WHEN cr.vend_crm IS NULL THEN 'sem_crm'
    WHEN UPPER(ca.salesperson_name) = UPPER(cr.vend_crm)
      OR UPPER(cr.vend_crm) LIKE CONCAT('%', UPPER(ca.salesperson_name), '%')
      OR UPPER(ca.salesperson_name) LIKE CONCAT('%', SPLIT(UPPER(cr.vend_crm), ' ')[OFFSET(0)], '%')
    THEN 'match_crm_carteira'
    ELSE 'diverge'
  END AS status
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` ca
LEFT JOIN erp_dom e ON e.partner_code = ca.partner_code AND e.rn = 1
LEFT JOIN crm_owner cr ON cr.partner_code = ca.partner_code
WHERE ca.is_active = TRUE
""").to_dataframe()

print(f'Total: {len(trip)}')
print('\nStatus carteira vs CRM:')
print(trip['status'].value_counts().to_string())

# Pivot familia × vendedor_crm
print('\n=== HOSPITALAR — distribuicao por VENDEDOR CRM ===')
hosp = trip[trip['rfv_familia']=='HOSPITALAR']
print(hosp['vend_crm'].value_counts(dropna=False).to_string())

print('\n=== Os 7 Giovanna HOSPITALAR — vista 3-fontes ===')
codes = [51693, 598, 47610, 47901, 914330, 46589, 51689]
print(trip[trip['partner_code'].isin(codes)][['partner_code','partner_name','vend_carteira','vend_erp','vend_crm','status']].to_string(index=False))
