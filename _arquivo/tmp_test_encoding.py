"""
Testa encodings do pyodbc contra SQL Server para achar qual resolve os '?'
nos nomes com caracteres especiais (ç, ã, é, etc.)
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

# Nomes que sabemos que estão corrompidos (para checar se voltam correto)
NAMES_TO_CHECK = [
    "FUNDA??O FACULDADE DE MEDICINA",      # → FUNDAÇÃO FACULDADE DE MEDICINA
    "CORUMB? HOSPITALAR EIRELI-ME",        # → CORUMBÁ HOSPITALAR EIRELI-ME
    "SERVI?OS",                            # → SERVIÇOS
    "UPMED FABRICA??O",                    # → UPMED FABRICAÇÃO
]

# Busca pelo código dos clientes que sabemos ter acento
KNOWN_CODES = [23624, 22570, 23006, 31599, 913644]  # dos diagnósticos

encodings_to_try = [
    ("sem setdecoding",      None, None, None),
    ("utf-8",                "utf-8",   "utf-8",      "utf-8"),
    ("cp1252 (Windows)",     "cp1252",  "utf-16-le",  "cp1252"),
    ("latin-1",              "latin-1", "utf-16-le",  "latin-1"),
    ("utf-8 / utf-16-le",   "utf-8",   "utf-16-le",  "utf-8"),
]

print("Buscando nomes para os códigos:", KNOWN_CODES)
print("=" * 70)

for label, char_enc, wchar_enc, set_enc in encodings_to_try:
    try:
        conn = pyodbc.connect(CONN_BASE, timeout=15)
        if char_enc:
            conn.setdecoding(pyodbc.SQL_CHAR, encoding=char_enc)
        if wchar_enc:
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding=wchar_enc)
        if set_enc:
            conn.setencoding(encoding=set_enc)

        codes_str = ", ".join(str(c) for c in KNOWN_CODES)
        cur = conn.cursor()
        cur.execute(
            f"SELECT YCODCLI, YNOMCLI FROM [CLIENTES OU FORNECEDORES] "
            f"WHERE YTIPCLI = 'C' AND YCODCLI IN ({codes_str})"
        )
        rows = [(int(r[0]), str(r[1]).strip()) for r in cur.fetchall()]
        conn.close()

        has_question = any('?' in nome for _, nome in rows)
        has_accents  = any(any(c in nome for c in 'ÃÇÉÁÂÊÍÕÚãçéáâêíõú') for _, nome in rows)
        status = "✅ OK (acentos corretos)" if has_accents and not has_question else \
                 ("❌ ainda tem '?'" if has_question else "⚠️  sem acentos nem '?'")

        print(f"\n[{label}] {status}")
        for code, nome in rows:
            print(f"  {code}: {nome}")

    except Exception as e:
        print(f"\n[{label}] ERRO: {e}")

print("\n" + "=" * 70)
