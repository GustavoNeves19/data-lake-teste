"""Verifica se YNUMERO do Alves existe + lista outros bancos no servidor."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)

ex = SQLServerExtractor()
ex.connect()

# 1) Lista TODOS os bancos no servidor
print('=== BANCOS NO SERVIDOR ===')
df = pd.read_sql("SELECT name FROM sys.databases ORDER BY name", ex._conn)
print(df.to_string(index=False))

# 2) Verifica se o YNUMERO 199818A existe em COMPRAS E VENDAS
print('\n=== Pedido 199818A (que o Alves diz ser a nota 96550) ===')
df2 = pd.read_sql("""
SELECT TOP 10 YNUMERO, YNUMNOT, YTIPOPE, YDATEXC, YDATPED, YDATNOT, YCODEMP, YCODNAT, YVALTOT
FROM [COMPRAS E VENDAS]
WHERE YNUMERO = '199818A'
""", ex._conn)
print(df2.to_string(index=False))

# 3) Verifica se outros YNUMEROs do Alves existem
amostra = ['199818A', '199487A', '199492A', '199488A', '199493A', '199489A', '199819A', '199385A', '199380A', '199384A']
codes_str = ','.join(f"'{c}'" for c in amostra)
print(f'\n=== 10 pedidos da planilha Alves no ERP ===')
df3 = pd.read_sql(f"""
SELECT YNUMERO, YNUMNOT, YTIPOPE, YDATEXC, YDATPED, YDATNOT, YCODEMP, YVALTOT
FROM [COMPRAS E VENDAS]
WHERE YNUMERO IN ({codes_str})
""", ex._conn)
print(df3.to_string(index=False))
print(f'Encontrados: {len(df3)} de 10')
