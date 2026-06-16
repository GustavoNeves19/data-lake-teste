"""De onde vem a classificação Giovanna→HOSPITALAR? Planilha ou ERP?"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 200)
pd.set_option('display.max_colwidth', 60)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

codes_hosp = [51693, 598, 47610, 47901, 914330, 46589, 51689]

# 1) Planilha HOSPITALAR Alves
print('=' * 80)
print('1) PLANILHA Alves HOSPITALAR — quem cita "Giovanna"?')
print('=' * 80)
try:
    path = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026 (1).xlsx'
    df_e = pd.read_excel(path, sheet_name='Sem fórmula Geral')
    cols_vend = [c for c in df_e.columns if 'VEND' in c.upper() or 'RESPON' in c.upper() or 'ATEND' in c.upper()]
    print(f'Colunas vendedor encontradas: {cols_vend}')
    if cols_vend:
        for col in cols_vend:
            mask = df_e[col].astype(str).str.upper().str.contains('GIOVAN', na=False)
            print(f'\n  {col}: {mask.sum()} linhas mencionam Giovanna')
            if mask.any():
                show = df_e[mask][['ID - CLIENTE', col]].head(20)
                print(show.to_string(index=False))
    else:
        print('  Sem coluna vendedor na planilha HOSPITALAR.')
except Exception as e:
    print(f'  Erro: {e}')

# 2) ERP — YCODVEN2 desses clientes
print('\n' + '=' * 80)
print('2) ERP — vendedor (YCODVEN2) dos 7 clientes nos pedidos')
print('=' * 80)
ex = SQLServerExtractor()
ex.connect()
codes_str = ','.join(str(c) for c in codes_hosp)
df_erp = pd.read_sql(f"""
SELECT
  cv.YCODCLI AS partner_code,
  cv.YCODVEN2 AS vendedor_code,
  a.YNOMVEN AS vendedor_nome,
  COUNT(*) AS pedidos,
  MAX(cv.YDATPED) AS ultimo_pedido
FROM [COMPRAS E VENDAS] cv
LEFT JOIN [ATENDENTES] a ON a.YCODVEN = cv.YCODVEN2
WHERE cv.YCODCLI IN ({codes_str})
  AND cv.YTIPOPE = 'S'
  AND cv.YDATEXC IS NULL
  AND cv.YDATPED >= '2024-05-01'
GROUP BY cv.YCODCLI, cv.YCODVEN2, a.YNOMVEN
ORDER BY cv.YCODCLI, pedidos DESC
""", ex._conn)
print(df_erp.to_string(index=False))

print('\n' + '=' * 80)
print('3) Pivot — quem mais vende para cada cliente (vendedor dominante)')
print('=' * 80)
df_dom = df_erp.sort_values(['partner_code','pedidos'], ascending=[True,False]).groupby('partner_code').first().reset_index()
print(df_dom[['partner_code','vendedor_nome','pedidos','ultimo_pedido']].to_string(index=False))
