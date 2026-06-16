"""Investiga banco 'neXTGen - NSR' — onde estão as notas reais?"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import pyodbc
from dotenv import load_dotenv
from pathlib import Path

# Carrega .env
for _d in [Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents):
    if (_d / '.env').exists():
        load_dotenv(_d / '.env')
        break

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)

# Conecta no neXTGen - NSR
conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER_HOST')},{os.getenv('SQL_SERVER_PORT')};"
    f"DATABASE=neXTGen - NSR;"
    f"UID={os.getenv('SQL_SERVER_USER')};"
    f"PWD={os.getenv('SQL_SERVER_PASSWORD')};"
)
conn = pyodbc.connect(conn_str, timeout=30)

# 1) Lista tabelas do neXTGen
print('=== Tabelas com NOTA/VENDA/NF no neXTGen - NSR ===')
df = pd.read_sql("""
SELECT TABLE_NAME, TABLE_TYPE
FROM INFORMATION_SCHEMA.TABLES
WHERE UPPER(TABLE_NAME) LIKE '%NOTA%' OR UPPER(TABLE_NAME) LIKE '%VENDA%'
   OR UPPER(TABLE_NAME) LIKE '%COMPRA%' OR UPPER(TABLE_NAME) LIKE '%FISCAL%'
   OR UPPER(TABLE_NAME) LIKE '%NFE%'
ORDER BY TABLE_NAME
""", conn)
print(df.to_string(index=False))

# 2) Verifica COMPRAS E VENDAS no neXTGen
print('\n=== COMPRAS E VENDAS existe no neXTGen? ===')
df2 = pd.read_sql("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME = 'COMPRAS E VENDAS'
""", conn)
print(df2.to_string(index=False))

# 3) Se sim, busca a nota 96550
print('\n=== Nota 96550 no neXTGen ===')
try:
    df3 = pd.read_sql("""
    SELECT TOP 10
      YNUMNOT, YNUMERO, YTIPOPE, YDATEXC, YDATPED, YDATNOT,
      YCODCLI, YCODEMP, YCODNAT, YVALTOT
    FROM [COMPRAS E VENDAS]
    WHERE YNUMNOT = 96550
    """, conn)
    print(df3.to_string(index=False))
except Exception as e:
    print(f'Erro: {e}')

# 4) Stats gerais
print('\n=== Stats de COMPRAS E VENDAS no neXTGen ===')
try:
    df4 = pd.read_sql("""
    SELECT
      COUNT(*) AS total,
      MIN(YDATPED) AS min_pedido,
      MAX(YDATPED) AS max_pedido,
      MIN(YDATNOT) AS min_nota,
      MAX(YDATNOT) AS max_nota
    FROM [COMPRAS E VENDAS]
    WHERE YTIPOPE = 'S' AND YDATEXC IS NULL
    """, conn)
    print(df4.to_string(index=False))
except Exception as e:
    print(f'Erro: {e}')

# 5) Pedidos pos 12/05
print('\n=== Pedidos pos 12/05 no neXTGen ===')
try:
    df5 = pd.read_sql("""
    SELECT COUNT(*) AS qtd, SUM(YVALTOT) AS valor
    FROM [COMPRAS E VENDAS]
    WHERE YDATPED > '2026-05-12' AND YTIPOPE = 'S' AND YDATEXC IS NULL
    """, conn)
    print(df5.to_string(index=False))
except Exception as e:
    print(f'Erro: {e}')

conn.close()
