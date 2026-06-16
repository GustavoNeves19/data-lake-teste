import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

df = pd.read_csv('diagnostico_faltantes.csv', encoding='utf-8-sig')

print('=== CAMADA 5 — bq_nomes com encoding corrompido ===')
c5 = df[df['camada']==5]
print(f'Total: {len(c5)} clientes')
for _, r in c5.head(5).iterrows():
    print(f'  {r["familia"]} | bq_nome={repr(str(r["bq_nome"])[:55])} | fat_pot=R${float(r["fat_potencial"]):,.0f}')

print()
print('=== CAMADA 4 — faturamento excluído por natureza ===')
c4 = df[df['camada']==4]
print(f'Total: {len(c4)} clientes | fat_excluido_nature total: R$ {c4["fat_excluido_nature"].sum():,.2f}')
for _, r in c4.sort_values('fat_excluido_nature', ascending=False).iterrows():
    print(f'  {str(r["planilha_nome"])[:50]:<50} | R$ {float(r["fat_excluido_nature"]):>10,.2f} | {r["causa"]}')

print()
print('=== VERIFICAÇÃO — nomes corrompidos no BQ ===')
# Verificar quantos dos c5 realmente estao no resultado RFV com nome corrompido
creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform'])
client = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

codes_c5 = [int(x) for x in c5['partner_code'].dropna().tolist()]
if codes_c5:
    codes_str = ', '.join(str(c) for c in codes_c5)
    sql = f"""
    SELECT DISTINCT c.partner_code, c.partner_name, c.rfv_familia
    FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
    JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` c
      ON c.partner_code = o.partner_code AND c.is_active = TRUE
      AND c.salesperson_name NOT IN ('Eduardo', 'Karina')
    JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
      ON n.nature_code = o.nature_code AND n.financial_flag = 'F'
    WHERE o.order_status IN (3, 4)
      AND o.order_date BETWEEN DATE('2025-04-01') AND DATE('2026-04-30')
      AND c.partner_code IN ({codes_str})
    ORDER BY c.partner_code
    """
    rfv_c5 = client.query(sql).to_dataframe()
    print(f'Dos {len(codes_c5)} partner_codes da Camada 5, {len(rfv_c5)} aparecem no resultado RFV com nome corrompido:')
    for _, r in rfv_c5.iterrows():
        print(f'  [{int(r["partner_code"])}] {str(r["partner_name"])[:60]} ({r["rfv_familia"]})')
