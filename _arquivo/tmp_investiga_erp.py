"""Investiga: a nota 96550 (LHVMED, 20/05/2026, R$ 86k) existe no ERP?"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)

ex = SQLServerExtractor()
ex.connect()

# 1) Busca nota 96550 sem filtros
print('=== Nota 96550 (qualquer YTIPOPE, qualquer flag) ===')
df = pd.read_sql("""
SELECT TOP 5
  YNUMNOT AS nota, YNUMERO AS pedido, YTIPOPE, YDATEXC,
  YDATPED, YDATNOT, YDATSAI, YSTATUS,
  YCODCLI, YCODEMP, YCODNAT, YVALTOT
FROM [COMPRAS E VENDAS]
WHERE YNUMNOT = 96550
""", ex._conn)
print(df.to_string(index=False))

# 2) MAX/MIN do ERP por YDATNOT
print('\n=== Stats gerais YTIPOPE=S, YDATEXC IS NULL ===')
df2 = pd.read_sql("""
SELECT
  COUNT(*) AS total,
  MIN(YDATPED) AS min_pedido,
  MAX(YDATPED) AS max_pedido,
  MIN(YDATNOT) AS min_nota,
  MAX(YDATNOT) AS max_nota
FROM [COMPRAS E VENDAS]
WHERE YTIPOPE = 'S' AND YDATEXC IS NULL
""", ex._conn)
print(df2.to_string(index=False))

# 3) Quantos pedidos pós 12/05?
print('\n=== Pedidos com YDATPED > 12/05 ===')
df3 = pd.read_sql("""
SELECT YTIPOPE, COUNT(*) AS qtd
FROM [COMPRAS E VENDAS]
WHERE YDATPED > '2026-05-12'
GROUP BY YTIPOPE
""", ex._conn)
print(df3.to_string(index=False))

# 4) E pelo YDATNOT?
print('\n=== Notas (YDATNOT) > 12/05 ===')
df4 = pd.read_sql("""
SELECT YTIPOPE, COUNT(*) AS qtd, SUM(YVALTOT) AS valor
FROM [COMPRAS E VENDAS]
WHERE YDATNOT > '2026-05-12'
GROUP BY YTIPOPE
""", ex._conn)
print(df4.to_string(index=False))

# 5) Pega as 10 notas faltantes
notas_faltantes = [96550, 96334, 96436, 96366, 96628, 96757, 96371, 96518, 96578, 96379]
codes_str = ','.join(str(n) for n in notas_faltantes)
print(f'\n=== 10 notas faltantes — onde estão no ERP? ===')
df5 = pd.read_sql(f"""
SELECT YNUMNOT, YNUMERO, YTIPOPE, YDATEXC,
       YDATPED, YDATNOT, YSTATUS, YCODEMP, YCODNAT, YVALTOT
FROM [COMPRAS E VENDAS]
WHERE YNUMNOT IN ({codes_str})
""", ex._conn)
print(df5.to_string(index=False))

ex.close() if hasattr(ex, 'close') else None
