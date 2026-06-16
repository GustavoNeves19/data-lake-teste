"""
Inspeciona como os dados estão realmente armazenados no SQL Server ERP.
Verifica tipo da coluna, collation, e se existe versão Unicode dos nomes.
"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from dotenv import load_dotenv
import pyodbc

_dir = Path(__file__).resolve()
for _ in range(8):
    _dir = _dir.parent
    if (_dir / ".env").exists():
        load_dotenv(_dir / ".env")
        break

CONN_BASE = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER_HOST')},{os.getenv('SQL_SERVER_PORT')};"
    f"DATABASE={os.getenv('SQL_SERVER_DATABASE')};"
    f"UID={os.getenv('SQL_SERVER_USER')};"
    f"PWD={os.getenv('SQL_SERVER_PASSWORD')};"
)

KNOWN_CODES = [23624, 22570, 23006, 31599, 913644]
codes_str = ", ".join(str(c) for c in KNOWN_CODES)

conn = pyodbc.connect(CONN_BASE, timeout=15)
cur  = conn.cursor()

print("=" * 70)
print("1. Tipo e collation da coluna YNOMCLI")
print("=" * 70)
cur.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, COLLATION_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'CLIENTES OU FORNECEDORES'
      AND COLUMN_NAME IN ('YCODCLI','YNOMCLI','YNOMRED')
    ORDER BY COLUMN_NAME
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}({r[2]}) COLLATION={r[3]}")

print()
print("=" * 70)
print("2. Todas as colunas de nome disponíveis na tabela")
print("=" * 70)
cur.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'CLIENTES OU FORNECEDORES'
      AND (COLUMN_NAME LIKE '%NOM%' OR COLUMN_NAME LIKE '%NAME%' OR COLUMN_NAME LIKE '%RAZ%')
    ORDER BY COLUMN_NAME
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}({r[2]})")

print()
print("=" * 70)
print("3. Valores brutos com CONVERT para inspecionar bytes")
print("=" * 70)
cur.execute(f"""
    SELECT
        YCODCLI,
        YNOMCLI,
        CONVERT(VARBINARY(200), YNOMCLI) AS bytes_nome,
        LEN(YNOMCLI) AS len_nome,
        DATALENGTH(YNOMCLI) AS datalen_nome
    FROM [CLIENTES OU FORNECEDORES]
    WHERE YTIPCLI = 'C' AND YCODCLI IN ({codes_str})
""")
for r in cur.fetchall():
    raw_bytes = bytes(r[2]) if r[2] else b''
    nome = str(r[1]).strip() if r[1] else ''
    print(f"  Cod {int(r[0])}: '{nome}'")
    print(f"    LEN={r[3]} DATALENGTH={r[4]}")
    print(f"    bytes: {raw_bytes[:40].hex()}")
    # Tentar decodificar de diferentes formas
    for enc in ['utf-8', 'cp1252', 'latin-1', 'utf-16-le', 'cp850']:
        try:
            decoded = raw_bytes.decode(enc)
            if any(c in decoded for c in 'ÃÇÉÁÂÊÍÕÚãçéáâêíõú'):
                print(f"    ✅ decodificado como {enc}: '{decoded[:60]}'")
        except Exception:
            pass
    print()

print()
print("=" * 70)
print("4. Verificar se existe campo NVARCHAR equivalente")
print("=" * 70)
# Tenta buscar com N'' prefix para forçar unicode
try:
    cur.execute(f"""
        SELECT YCODCLI, CAST(YNOMCLI AS NVARCHAR(200)) as nome_n
        FROM [CLIENTES OU FORNECEDORES]
        WHERE YTIPCLI = 'C' AND YCODCLI IN ({codes_str})
    """)
    for r in cur.fetchall():
        print(f"  Cod {int(r[0])}: '{str(r[1]).strip()}'")
except Exception as e:
    print(f"  Erro: {e}")

print()
print("=" * 70)
print("5. Collation do banco e servidor")
print("=" * 70)
cur.execute("SELECT SERVERPROPERTY('Collation') AS server_collation, DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS db_collation")
for r in cur.fetchall():
    print(f"  Server collation: {r[0]}")
    print(f"  Database collation: {r[1]}")

conn.close()
