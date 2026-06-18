"""
Watcher de frescor do pipeline (uso pontual, monitoramento overnight).

Acompanha o run do ETL na nuvem (EasyPanel) lendo o last_modified das tabelas
no BigQuery — independente do navegador. Imprime um snapshot a cada ciclo e
para quando o pipeline COMPLETA (ERP -> silver -> gold todos frescos) ou no timeout.

Não faz parte do pipeline de produção — é só instrumentação de observabilidade.
"""
import os
import sys
import io
import time
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", r"C:\teste\sapient-metrics.json")
from google.cloud import bigquery  # noqa: E402

PROJECT = "sapient-metrics-492914-m7"
DATASETS = ["dm_orders", "dm_partners", "silver_comercial", "gold_comercial"]

# critérios de "pipeline completou": ERP (orders) fresco E todo o gold fresco
ERP_TABLE = "fact_sales_order"
ERP_FRESH_MIN = 30.0
GOLD_FRESH_MIN = 15.0

POLL_SECONDS = 90
TIMEOUT_MIN = 55


def age_min(ts, now):
    if ts is None:
        return None
    return (now - ts).total_seconds() / 60.0


def snapshot(client):
    now = datetime.now(timezone.utc)
    rows = {}
    for ds in DATASETS:
        try:
            tables = list(client.list_tables(f"{PROJECT}.{ds}"))
        except Exception as e:  # dataset pode nem existir ainda
            rows[ds] = {"_error": str(e)[:80]}
            continue
        d = {}
        for t in tables:
            try:
                tbl = client.get_table(f"{PROJECT}.{ds}.{t.table_id}")
                d[t.table_id] = (age_min(tbl.modified, now), tbl.num_rows)
            except Exception as e:
                d[t.table_id] = (None, str(e)[:40])
        rows[ds] = d
    return now, rows


def main():
    client = bigquery.Client(project=PROJECT)
    start = time.monotonic()
    cycle = 0
    print(f"=== WATCHER iniciado {datetime.now(timezone.utc).isoformat()} UTC ===", flush=True)
    print(f"Critério de sucesso: {ERP_TABLE} < {ERP_FRESH_MIN}min E todo gold_comercial < {GOLD_FRESH_MIN}min\n", flush=True)

    while True:
        cycle += 1
        elapsed = (time.monotonic() - start) / 60.0
        now, rows = snapshot(client)
        print(f"\n----- ciclo {cycle} | {now.strftime('%H:%M:%S')} UTC | +{elapsed:.1f}min -----", flush=True)

        for ds in DATASETS:
            d = rows.get(ds, {})
            if "_error" in d:
                print(f"  [{ds}] (indisponível: {d['_error']})", flush=True)
                continue
            print(f"  [{ds}]", flush=True)
            for tid in sorted(d):
                age, info = d[tid]
                if age is None:
                    print(f"      {tid:<34} erro={info}", flush=True)
                else:
                    flag = "FRESCO" if age < GOLD_FRESH_MIN else ""
                    print(f"      {tid:<34} {age:7.1f} min   linhas={info}  {flag}", flush=True)

        # avaliar critério de conclusão
        erp = rows.get("dm_orders", {}).get(ERP_TABLE)
        erp_age = erp[0] if erp else None
        gold = rows.get("gold_comercial", {})
        gold_ages = [v[0] for v in gold.values() if isinstance(v, tuple) and v[0] is not None]

        # gold_qa_validacao NÃO faz parte do pipeline diário (script separado, usa pyodbc).
        # Só os gold_com_* são reconstruídos por run_gold_comercial.py.
        gold_core = {k: v for k, v in gold.items()
                     if k.startswith("gold_com_") and isinstance(v, tuple) and v[0] is not None}
        gold_core_ages = [v[0] for v in gold_core.values()]

        erp_ok = erp_age is not None and erp_age < ERP_FRESH_MIN
        gold_ok = len(gold_core_ages) >= 4 and max(gold_core_ages) < GOLD_FRESH_MIN

        print(f"  >> ERP fresco={erp_ok} (age={erp_age}) | gold fresco={gold_ok} "
              f"(max={max(gold_ages) if gold_ages else None})", flush=True)

        if erp_ok and gold_ok:
            print("\n=== PIPELINE COMPLETO: ERP + silver + gold frescos. SUCESSO. ===", flush=True)
            return 0

        if elapsed > TIMEOUT_MIN:
            print(f"\n=== TIMEOUT ({TIMEOUT_MIN}min) sem completar. Verificar logs do EasyPanel. ===", flush=True)
            return 2

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
