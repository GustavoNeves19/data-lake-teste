# -*- coding: utf-8 -*-
"""Runner temporario: executa rfv_classificacao_erp.sql no ERP e imprime as 3 saidas.
Uso: py -3 scripts/_run_rfv_erp_tmp.py [YYYY-MM-DD]
"""
import io, os, sys
import pyodbc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SQL_SERVER_CONFIG as cfg
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

data_ref = sys.argv[1] if len(sys.argv) > 1 else None

sql_path = os.path.join(os.path.dirname(__file__), "rfv_classificacao_erp.sql")
sql = open(sql_path, encoding="utf-8").read()
if data_ref:
    sql = sql.replace("DECLARE @DataRef DATE = CAST(GETDATE() AS DATE);",
                      f"DECLARE @DataRef DATE = '{data_ref}';")

cn = pyodbc.connect(
    f"DRIVER={{{cfg['driver']}}};SERVER={cfg['server']},{cfg['port']};"
    f"DATABASE={cfg['database']};UID={cfg['uid']};PWD={cfg['pwd']};"
    "TrustServerCertificate=yes;Connection Timeout=30;",
    readonly=True,
)
cur = cn.cursor()
cur.execute(sql)

titulos = ["SAIDA 1 - GERAL por segmento", "SAIDA 2 - por familia", "SAIDA 3 - headline"]
i = 0
while True:
    if cur.description:
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print("\n" + "=" * 92)
        print(f"  {titulos[i] if i < len(titulos) else 'resultado'}")
        print("=" * 92)
        w = [max(len(str(c)), *(len(f'{r[j]:,}' if isinstance(r[j], int) else str(r[j])) for r in rows)) if rows else len(str(c)) for j, c in enumerate(cols)]
        print("  " + " | ".join(str(c).ljust(w[j]) for j, c in enumerate(cols)))
        print("  " + "-+-".join("-" * w[j] for j in range(len(cols))))
        for r in rows:
            cells = []
            for j, v in enumerate(r):
                s = f"{v:,}" if isinstance(v, int) else (f"{v:,.2f}" if isinstance(v, float) else str(v))
                cells.append(s.ljust(w[j]))
            print("  " + " | ".join(cells))
        i += 1
    if not cur.nextset():
        break
cn.close()
print("\nFim.")
