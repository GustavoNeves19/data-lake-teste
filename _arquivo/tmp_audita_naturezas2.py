"""Auditoria com nome correto da tabela (com Ç)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 70)
pd.set_option('display.max_rows', 300)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

ex = SQLServerExtractor()
ex.connect()

# 1) Schema completo da tabela
print('=== Colunas de [NATUREZAS DE OPERAÇÕES] ===')
df_cols = pd.read_sql("""
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = N'NATUREZAS DE OPERAÇÕES'
ORDER BY ORDINAL_POSITION
""", ex._conn)
print(df_cols.to_string(index=False))

# 2) Conteudo: todas as naturezas + flags
print('\n=== Snapshot completo de [NATUREZAS DE OPERAÇÕES] ===')
df_erp = pd.read_sql("""
SELECT *
FROM [NATUREZAS DE OPERAÇÕES]
ORDER BY YCODNAT
""", ex._conn)
print(f'Total no ERP: {len(df_erp)}')
print(f'\nPrimeiras 5 linhas:')
print(df_erp.head().to_string(index=False))

# 3) Dim do BQ
df_bq = c.query("""
SELECT *
FROM `sapient-metrics-492914-m7.dm_orders.dim_operation_nature`
""").to_dataframe()
print(f'\n=== dim_operation_nature do BQ ===')
print(f'Total: {len(df_bq)}')

# 4) Match codigos
codes_erp = set(df_erp['YCODNAT'].astype(str).str.strip())
codes_bq  = set(df_bq['nature_code'].astype(str).str.strip())

print(f'\n=== Match codigos ===')
print(f'  ERP: {len(codes_erp)}')
print(f'  BQ:  {len(codes_bq)}')
print(f'  Em ambos:         {len(codes_erp & codes_bq)}')
print(f'  So no ERP (faltam no BQ): {len(codes_erp - codes_bq)}')
print(f'  So no BQ (extras vs ERP): {len(codes_bq - codes_erp)}')

so_erp = sorted(codes_erp - codes_bq)
if so_erp:
    print(f'\n  Codigos so no ERP (faltam no BQ):')
    print(', '.join(so_erp[:50]))

so_bq = sorted(codes_bq - codes_erp)
if so_bq:
    print(f'\n  Codigos so no BQ (extras):')
    print(', '.join(so_bq[:50]))

# 5) Distribuicao das flags YFINNAT no ERP
print('\n=== Distribuicao YFINNAT (financial_flag) no ERP ===')
flag_col = [c for c in df_erp.columns if 'FIN' in c.upper()][0]
print(f'Coluna: {flag_col}')
print(df_erp[flag_col].value_counts(dropna=False).to_string())

# 6) Naturezas que estao no ERP mas com flag estranha (nem F nem N nem P nem E)
flags_validas = {'F', 'N', 'P', 'E'}
flag_unicas = set(df_erp[flag_col].dropna().astype(str).str.strip().unique())
flags_estranhas = flag_unicas - flags_validas
if flags_estranhas:
    print(f'\n⚠ Flags fora do esperado: {flags_estranhas}')
    for f in flags_estranhas:
        amostra = df_erp[df_erp[flag_col] == f].head(5)
        print(f'\n  Amostra YFINNAT={f}:')
        print(amostra[['YCODNAT', 'YNOMNAT' if 'YNOMNAT' in df_erp.columns else flag_col, flag_col]].to_string(index=False))

# 7) NULL flag — possivel problema
print(f'\n=== Naturezas com YFINNAT NULL ===')
null_flag = df_erp[df_erp[flag_col].isna()]
print(f'Total: {len(null_flag)}')
if len(null_flag) > 0:
    print(null_flag[['YCODNAT'] + ([c for c in null_flag.columns if 'NOM' in c.upper()][:1])].head(20).to_string(index=False))
