"""Auditoria completa: dim_operation_nature (BQ) x tabela NATUREZAS no ERP."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 70)
pd.set_option('display.max_rows', 200)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# 1) Descobre nome da tabela de naturezas no ERP
ex = SQLServerExtractor()
ex.connect()
print('=== Tabelas com "NATUREZA" no ERP ===')
df = pd.read_sql("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE UPPER(TABLE_NAME) LIKE '%NATUREZA%' OR UPPER(TABLE_NAME) LIKE '%OPERACAO%'
   OR UPPER(TABLE_NAME) LIKE '%NATURE%'
ORDER BY TABLE_NAME
""", ex._conn)
print(df.to_string(index=False))

# 2) Conferir colunas da tabela NATUREZAS DE OPERACOES (assumindo nome)
print('\n=== Colunas da tabela [NATUREZAS DE OPERACOES] ===')
df_cols = pd.read_sql("""
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'NATUREZAS DE OPERACOES'
ORDER BY ORDINAL_POSITION
""", ex._conn)
print(df_cols.to_string(index=False))
