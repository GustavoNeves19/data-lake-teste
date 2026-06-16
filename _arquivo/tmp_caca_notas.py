"""Caça as 4063 notas do Alves no banco NSR_ERP — onde estão?"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)

ex = SQLServerExtractor()
ex.connect()

# 1) Lista tabelas com "NOTA" ou "FISCAL" no nome
print('=== Tabelas com "NOTA"/"FISCAL"/"NF" no nome ===')
df = pd.read_sql("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE='BASE TABLE'
  AND (UPPER(TABLE_NAME) LIKE '%NOTA%' OR UPPER(TABLE_NAME) LIKE '%FISCAL%'
       OR UPPER(TABLE_NAME) = 'NF' OR UPPER(TABLE_NAME) LIKE '%NFE%')
ORDER BY TABLE_NAME
""", ex._conn)
print(df.to_string(index=False))

# 2) Lista views relacionadas
print('\n=== Views com NOTA/NF ===')
dfv = pd.read_sql("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.VIEWS
WHERE UPPER(TABLE_NAME) LIKE '%NOTA%' OR UPPER(TABLE_NAME) LIKE '%FISCAL%'
   OR UPPER(TABLE_NAME) = 'NF' OR UPPER(TABLE_NAME) LIKE '%NFE%'
ORDER BY TABLE_NAME
""", ex._conn)
print(dfv.to_string(index=False))

# 3) Lista TODAS as tabelas com YNUMNOT (que tem o campo de numero da nota)
print('\n=== Tabelas com a coluna YNUMNOT ===')
df3 = pd.read_sql("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE UPPER(COLUMN_NAME) = 'YNUMNOT'
ORDER BY TABLE_NAME
""", ex._conn)
print(df3.to_string(index=False))

# 4) Lista TODAS as tabelas com YIDENFE (chave NFe)
print('\n=== Tabelas com a coluna YIDENFE (chave NFe 44 dig) ===')
df4 = pd.read_sql("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE UPPER(COLUMN_NAME) = 'YIDENFE'
ORDER BY TABLE_NAME
""", ex._conn)
print(df4.to_string(index=False))
