"""
Cria o dataset gold_price e executa build_gold_price.sql.

Executar: py -3 sql/gold_price/run_gold_price.py

Tabelas criadas:
  param_price_custos  — camada MANUAL editável pelo app (custo/percentuais)
  gold_price_margem   — FATOS do ERP por produto × canal (faturamento, ICMS, IPI)

Ver docs/PAINEL_PRICE.md para o que é real (ERP) vs manual e a fórmula de margem.
"""
import io, os, re, sys, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# cloud: usa a env já setada; dev local: cai pro arquivo (sem sobrescrever a nuvem)
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')
from google.cloud import bigquery

BQ_PROJECT = 'sapient-metrics-492914-m7'
DATASET_ID = 'gold_price'
LOCATION   = 'us-east1'
SQL_FILE   = Path(__file__).parent / 'build_gold_price.sql'

client = bigquery.Client(project=BQ_PROJECT, location=LOCATION)


def ensure_dataset() -> None:
    dataset_ref = f'{BQ_PROJECT}.{DATASET_ID}'
    try:
        client.get_dataset(dataset_ref)
        print(f'  Dataset {DATASET_ID} já existe.')
    except Exception:
        ds = bigquery.Dataset(dataset_ref)
        ds.location = LOCATION
        client.create_dataset(ds)
        print(f'  Dataset {DATASET_ID} criado em {LOCATION}.')


def _strip_line_comments(sql: str) -> str:
    """Remove comentários de linha (-- ...) para que ; ou aspas dentro de
    comentário não corrompam o split. Nossas queries não têm '--' dentro de
    string literal, então o corte simples por linha é seguro."""
    out = []
    for ln in sql.splitlines():
        idx = ln.find('--')
        out.append(ln if idx < 0 else ln[:idx])
    return '\n'.join(out)


def split_statements(sql: str) -> list[str]:
    """Divide SQL em statements separados por ; (ignora ; dentro de strings)."""
    sql = _strip_line_comments(sql)
    stmts = []
    buf = []
    in_string = False
    string_char = ''
    for char in sql:
        if in_string:
            buf.append(char)
            if char == string_char:
                in_string = False
        elif char in ("'", '"'):
            in_string = True
            string_char = char
            buf.append(char)
        elif char == ';':
            stmt = ''.join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
        else:
            buf.append(char)
    last = ''.join(buf).strip()
    if last:
        stmts.append(last)
    return stmts


def run_statement(sql: str, label: str) -> None:
    t0 = time.time()
    job = client.query(sql)
    job.result()
    elapsed = time.time() - t0
    tbl_ref = f'{BQ_PROJECT}.{DATASET_ID}.{label}'
    try:
        tbl = client.get_table(tbl_ref)
        print(f'  ✅ {label}: {tbl.num_rows:,} linhas ({elapsed:.1f}s)')
    except Exception:
        print(f'  ✅ {label}: executado ({elapsed:.1f}s)')


def main() -> int:
    print('=' * 72)
    print('run_gold_price — Gold layer Painel PRICE (margem produto × canal)')
    print('=' * 72)

    print('\n[1/3] Verificando dataset...')
    ensure_dataset()

    print('\n[2/3] Lendo SQL...')
    sql = SQL_FILE.read_text(encoding='utf-8')
    stmts = split_statements(sql)
    # Filtra blocos sem SQL real (só comentários ou whitespace)
    stmts = [s for s in stmts if re.search(r'\b(CREATE|INSERT|UPDATE|DELETE|DROP|ALTER|WITH|SELECT)\b', s, re.IGNORECASE)]
    print(f'  {len(stmts)} statements encontrados.')

    print('\n[3/3] Executando...')
    for i, stmt in enumerate(stmts, 1):
        m = re.search(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?`[^`]*\.([^`\.]+)`', stmt, re.IGNORECASE)
        label = m.group(1) if m else f'stmt_{i}'
        print(f'\n  [{i}/{len(stmts)}] {label}...')
        run_statement(stmt, label)

    print()
    print('=' * 72)
    print('Gold Price criado em gold_price:')
    for tbl in client.list_tables(f'{BQ_PROJECT}.{DATASET_ID}'):
        t = client.get_table(f'{BQ_PROJECT}.{DATASET_ID}.{tbl.table_id}')
        print(f'  {t.table_id:<35} {t.num_rows:>7,} linhas')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
