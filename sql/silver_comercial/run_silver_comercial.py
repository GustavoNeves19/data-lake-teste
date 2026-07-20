"""
Executor do build_silver_comercial.sql contra BigQuery Nevoni/prod.

- Cria dataset silver_comercial se não existir
- Divide o arquivo .sql em statements individuais
- Roda cada statement em ordem, reportando sucesso/erro e contagem de linhas

Executar: py -3 sql/silver_comercial/run_silver_comercial.py

NOTA IMPORTANTE ANTES DA PRIMEIRA CARGA:
  A tabela param_com_rfv_carteira é criada vazia.
  Execute populate_carteira.py para populá-la com os clientes das planilhas RFV.
  Só depois execute este script para popular as demais tabelas silver.
"""
import io
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID  = "sapient-metrics-492914-m7"
DATASET_ID  = "silver_comercial"
LOCATION    = "us-east1"
CREDENTIALS = r"C:\teste\sapient-metrics.json"

SQL_FILE = Path(__file__).parent / "build_silver_comercial.sql"

# cloud: usa a GOOGLE_APPLICATION_CREDENTIALS já setada no ambiente;
# dev local: cai pro arquivo em C:\teste (não sobrescreve a env da nuvem).
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", CREDENTIALS)


# ── Parse SQL ─────────────────────────────────────────────────────────────────

def split_statements(sql_text: str) -> List[Tuple[str, str]]:
    cleaned_lines = []
    for line in sql_text.splitlines():
        if '--' in line:
            idx = line.find('--')
            line = line[:idx]
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    raw_statements = [s.strip() for s in cleaned.split(';')]
    statements = [s for s in raw_statements if s and not s.isspace()]

    labeled = []
    for stmt in statements:
        m = re.search(
            r'(CREATE\s+OR\s+REPLACE\s+TABLE|INSERT\s+INTO|CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?)\s+`?([\w.\-`]+)`?',
            stmt, re.IGNORECASE
        )
        if m:
            kind   = re.sub(r'\s+', ' ', m.group(1).upper())
            target = m.group(2).replace('`', '')
            label  = f"{kind} {target}"
        else:
            label  = stmt.strip().split('\n', 1)[0][:120]
        labeled.append((label, stmt))
    return labeled


# ── BQ helpers ────────────────────────────────────────────────────────────────

def ensure_dataset(client: bigquery.Client) -> None:
    ds_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    try:
        client.get_dataset(ds_ref)
        print(f"[dataset] {PROJECT_ID}.{DATASET_ID} ja existe")
    except NotFound:
        ds = bigquery.Dataset(ds_ref)
        ds.location = LOCATION
        ds.description = "Silver Comercial — RFV Nevoni (Hospitalar, Farmacias, SAC)"
        client.create_dataset(ds)
        print(f"[dataset] CRIADO: {PROJECT_ID}.{DATASET_ID} (location={LOCATION})")


def run_statement(client: bigquery.Client, label: str, stmt: str) -> Tuple[bool, str]:
    try:
        t0  = time.time()
        job = client.query(stmt)
        job.result()
        dt  = time.time() - t0

        info = f"{dt:.1f}s"
        if job.num_dml_affected_rows is not None:
            info += f" | dml_rows={job.num_dml_affected_rows}"
        if job.destination:
            try:
                tbl   = client.get_table(job.destination)
                info += f" | rows={tbl.num_rows}"
            except Exception:
                pass
        return True, info
    except Exception as e:
        return False, f"ERRO: {type(e).__name__}: {str(e)[:600]}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 78)
    print(f"Build silver_comercial em {PROJECT_ID}.{DATASET_ID}")
    print("=" * 78)

    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
    ensure_dataset(client)

    if not SQL_FILE.exists():
        print(f"[fatal] SQL nao encontrado em {SQL_FILE}")
        return 2

    sql_text   = SQL_FILE.read_text(encoding='utf-8')
    statements = split_statements(sql_text)
    print(f"[parse] {len(statements)} statements detectados\n")

    results = []
    for i, (label, stmt) in enumerate(statements, 1):
        print(f"[{i:02d}/{len(statements)}] {label}")
        ok, info = run_statement(client, label, stmt)
        status   = "OK  " if ok else "FAIL"
        print(f"     {status} | {info}\n")
        results.append((i, label, ok, info))

    # ── Resumo ────────────────────────────────────────────────────────────────
    print("=" * 78)
    print("RESUMO FINAL")
    print("=" * 78)
    ok_count   = sum(1 for _, _, ok, _ in results if ok)
    fail_count = len(results) - ok_count
    print(f"OK:   {ok_count}")
    print(f"FAIL: {fail_count}")
    print()

    tables = list(client.list_tables(f"{PROJECT_ID}.{DATASET_ID}"))
    print(f"Tabelas em {DATASET_ID}: {len(tables)}")
    for t in sorted(tables, key=lambda x: x.table_id):
        try:
            full = client.get_table(t.reference)
            print(
                f"  - {full.table_id:<55} "
                f"rows={full.num_rows:>10,}  "
                f"{full.num_bytes/1024/1024:>7.2f} MB"
            )
        except Exception as e:
            print(f"  - {t.table_id}  (erro: {e})")

    if fail_count:
        print("\nStatements com falha:")
        for i, label, ok, info in results:
            if not ok:
                print(f"  [{i:02d}] {label}")
                print(f"       {info}")

    if ok_count > 0 and fail_count == 0:
        print()
        print("=" * 78)
        print("PROXIMOS PASSOS:")
        print("  1. Verificar silver_com_rfv_resumo no BQ Console")
        print("  2. Comparar totais com planilha Alves (Resultado RFV / Resultado Geral)")
        print("  3. Ajustar param_com_rfv_carteira se clientes estiverem faltando")
        print("=" * 78)

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
