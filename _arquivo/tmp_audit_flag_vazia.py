"""Investiga as 7 naturezas com YFINNAT vazia + valida impacto no nosso filtro."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 70)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

ex = SQLServerExtractor()
ex.connect()

# 1) Lista as 7 com flag vazia
print('=== As 7 naturezas com YFINNAT vazia (ERP) ===')
df = pd.read_sql("""
SELECT YCODNAT, YNOMNAT, YFINNAT, YESTNAT, YENTSAI, YTIPMOV
FROM [NATUREZAS DE OPERAÇÕES]
WHERE YFINNAT = '' OR YFINNAT IS NULL
ORDER BY YCODNAT
""", ex._conn)
print(df.to_string(index=False))

# 2) Como o BQ trata essas no dim_operation_nature?
print('\n=== Mesma natureza no BQ (dim_operation_nature) ===')
codes = ','.join(f"'{c}'" for c in df['YCODNAT'])
df_bq = c.query(f"""
SELECT nature_code, nature_name, financial_flag, stock_movement_type, direction, is_return
FROM `sapient-metrics-492914-m7.dm_orders.dim_operation_nature`
WHERE nature_code IN ({codes})
ORDER BY nature_code
""").to_dataframe()
print(df_bq.to_string(index=False))

# 3) IMPACTO: essas 7 entram no faturamento via filtro <>N?
print('\n=== Impacto: faturamento que essas 7 geraram (12m) ===')
df_imp = c.query(f"""
SELECT
  nature_code,
  COUNT(*) AS pedidos,
  COUNT(DISTINCT partner_code) AS clientes,
  ROUND(SUM(total_amount), 2) AS faturamento
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE nature_code IN ({codes})
  AND order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
GROUP BY 1 ORDER BY faturamento DESC
""").to_dataframe()
print(df_imp.to_string(index=False))
print(f'\nTotal impacto: R$ {df_imp["faturamento"].sum() if not df_imp.empty else 0:,.2f}')

# 4) Validacao reversa: as flags F sao realmente faturamento? Quais geram saida?
print('\n=== Cruzamento: tipos de natureza por YENTSAI e YFINNAT ===')
df_cross = pd.read_sql("""
SELECT YENTSAI, YFINNAT, COUNT(*) AS qtd_naturezas
FROM [NATUREZAS DE OPERAÇÕES]
WHERE YDATEXC IS NULL
GROUP BY YENTSAI, YFINNAT
ORDER BY YENTSAI, YFINNAT
""", ex._conn)
print(df_cross.to_string(index=False))

# 5) Naturezas YENTSAI='S' (saida) com YFINNAT='N' — essas sao "vendas que nao geram faturamento"
print('\n=== Saidas (YENTSAI=S) com YFINNAT=N (importante!) ===')
df_s_n = pd.read_sql("""
SELECT YCODNAT, YNOMNAT, YESTNAT, YDEVNAT
FROM [NATUREZAS DE OPERAÇÕES]
WHERE YENTSAI = 'S' AND YFINNAT = 'N' AND YDATEXC IS NULL
ORDER BY YCODNAT
""", ex._conn)
print(f'Total: {len(df_s_n)}')
print(df_s_n.head(40).to_string(index=False))

# 6) Quanto faturamento ESSAS naturezas (saida + flag N) movimentam em valor?
print('\n=== Faturamento "perdido" pelo filtro <>N (saidas com flag N) ===')
codes_s_n = ','.join(f"'{c}'" for c in df_s_n['YCODNAT'])
if codes_s_n:
    df_perd = c.query(f"""
    SELECT
      nature_code,
      COUNT(*) AS qtd,
      ROUND(SUM(total_amount), 2) AS valor
    FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
    WHERE nature_code IN ({codes_s_n})
      AND order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    GROUP BY 1 ORDER BY valor DESC
    """).to_dataframe()
    print(f'Naturezas com movimento: {len(df_perd)}')
    print(df_perd.head(30).to_string(index=False))
    print(f'\nTotal: R$ {df_perd["valor"].sum() if not df_perd.empty else 0:,.2f}')
