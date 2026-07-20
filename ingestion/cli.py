"""
CLI do framework de ingestão.

    py -3 -m ingestion ingest    --source umbler [--entity channels chats] [--full]
    py -3 -m ingestion test      --source umbler
    py -3 -m ingestion list      --source umbler
    py -3 -m ingestion sources
    py -3 -m ingestion freshness
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import structlog

from config.settings import ENVIRONMENT
from ingestion.registry import load_source, list_sources
from ingestion.connectors import get_connector
from ingestion.runner import IngestionRunner
from ingestion.state import IngestionState


def _setup_logging() -> None:
    processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    processors.append(
        structlog.processors.JSONRenderer() if ENVIRONMENT == "production"
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ── Comandos ─────────────────────────────────────────────────────────────────

def cmd_sources() -> int:
    print("\nFontes registradas (config/sources/*.json):")
    for name in list_sources():
        src = load_source(name)
        print(f"  • {name:12s} → {src.dataset:14s} [{len(src.entities)} entidades] conector={src.connector}")
    print()
    return 0


def cmd_list(source: str) -> int:
    src = load_source(source)
    print(f"\n═══ {src.source} — {len(src.entities)} entidades → {src.dataset} ═══\n")
    print(f"  {'Entidade':<26} {'Projeção':<9} {'Modo':<9} {'Detalhe'}")
    print(f"  {'─'*26} {'─'*9} {'─'*9} {'─'*30}")
    for name, cfg in src.entities.items():
        proj = cfg.get("projection", "envelope")
        if proj == "typed":
            detalhe = f"kind={cfg.get('kind')}" + (f" pipeline={cfg['pipeline_id']}" if cfg.get("pipeline_id") else "")
        else:
            detalhe = f"{cfg.get('pagination_mode','')}  {cfg.get('endpoint','')}"
        print(f"  {name:<26} {proj:<9} {cfg.get('write_mode',''):<9} {detalhe}")
    print()
    return 0


def cmd_test(source: str) -> int:
    src = load_source(source)
    connector = get_connector(src.connector)
    print(f"\n═══ Teste de conexão — {src.source} ═══")
    try:
        info = connector.test_connection()
        for k, v in info.items():
            print(f"  ✓ {k}: {v}")
        print()
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ ERRO: {e}\n")
        return 1


def cmd_ingest(source: str, entities: list[str] | None, full: bool) -> int:
    runner = IngestionRunner()
    scope = "todas" if not entities else ", ".join(entities)
    print(f"\n═══ Ingestão {source.upper()} — entidades: {scope}{'  [FULL]' if full else ''} ═══\n")

    result = runner.run_source(source, entities_filter=entities, full=full)

    print(f"\n{'═'*64}")
    print(f"  run_id: {result.run_id}  |  {result.total_seconds}s")
    print(f"  ✓ OK: {result.ok}   ✗ Erro: {result.errors}   ⊘ Vazio: {result.skipped}   linhas: {result.total_rows:,}")
    print(f"{'═'*64}\n")
    print(f"  {'Entidade':<14} {'Status':<8} {'Extraído':>10} {'Carregado':>10} {'Tempo':>7}  Watermark")
    print(f"  {'─'*14} {'─'*8} {'─'*10} {'─'*10} {'─'*7}  {'─'*20}")
    for d in result.details:
        icon = "✓" if d.status == "ok" else ("✗" if d.status == "error" else "⊘")
        print(f"  {d.entity:<14} {icon} {d.status:<6} {d.rows_extracted:>10,} {d.rows_loaded:>10,} "
              f"{d.seconds:>6.1f}s  {d.max_event_at or ''}")
    errs = [d for d in result.details if d.status == "error"]
    if errs:
        print("\n  ⚠ Erros:")
        for d in errs:
            print(f"    • {d.entity}: {d.error}")
    print()
    return 1 if result.errors else 0


def cmd_daily(exclude: list[str] | None) -> int:
    """Roda TODAS as fontes de API registradas (Gmail, Pipedrive, Umbler, ClickUp,
    Miro) numa tacada. O ERP NÃO entra — não é fonte registrada (é o main.py à parte,
    que depende da carga do banco do Diego). Pensado pro agendador da nuvem (manhã).

    Continua mesmo se uma fonte falhar; retorna != 0 se qualquer uma deu erro,
    pro Cloud Scheduler/Run marcar a execução como falha e alertar.
    """
    runner = IngestionRunner()
    exclude = set(exclude or [])
    sources = [s for s in list_sources() if s not in exclude]

    print(f"\n{'═'*64}")
    print(f"  CARGA DIÁRIA — {len(sources)} fontes: {', '.join(sources)}")
    if exclude:
        print(f"  (excluídas: {', '.join(sorted(exclude))})")
    print(f"{'═'*64}")

    tot_ok = tot_err = tot_skip = tot_rows = 0
    falhas: list[str] = []
    # Linha de auditoria por fonte: ícone, rows e tempo — preenchida mesmo em falha total.
    audit: list[dict] = []
    for src in sources:
        t0 = time.time()
        try:
            r = runner.run_source(src, full=False)
            tot_ok += r.ok; tot_err += r.errors; tot_skip += r.skipped; tot_rows += r.total_rows
            icon = "✓" if r.errors == 0 else "✗"
            print(f"  {icon} {src:12s} ok={r.ok} erro={r.errors} vazio={r.skipped} "
                  f"linhas={r.total_rows:,} ({r.total_seconds}s)")
            # ⊘ vazio só quando NADA carregou e não houve erro (skip total da fonte).
            if r.errors:
                status_icon = "❌"
            elif r.total_rows == 0 and r.ok == 0:
                status_icon = "⊘"
            else:
                status_icon = "✅"
            first_err = next((d.error for d in r.details if d.status == "error"), "")
            audit.append({"src": src, "icon": status_icon, "rows": r.total_rows,
                          "seconds": r.total_seconds, "error": first_err})
            if r.errors:
                falhas.append(src)
        except Exception as e:  # noqa: BLE001
            falhas.append(src)
            print(f"  ✗ {src:12s} FALHA TOTAL: {e}")
            audit.append({"src": src, "icon": "❌", "rows": 0,
                          "seconds": round(time.time() - t0, 2), "error": str(e)})

    print(f"{'═'*64}")
    print(f"  TOTAL: {tot_ok} ok · {tot_err} erro · {tot_skip} vazio · {tot_rows:,} linhas")
    if falhas:
        print(f"  ⚠ Fontes com erro: {', '.join(falhas)}")
    print(f"{'═'*64}\n")

    # ── Auditoria: uma linha por fonte com status visual (✅/❌/⊘) ────────────────
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"{'═'*64}")
    print(f"  === RESUMO DA CARGA (auditoria) ===   {ts}")
    print(f"{'═'*64}")
    print(f"  {'':2s} {'Fonte':<12} {'Linhas':>10} {'Tempo':>8}  Detalhe")
    print(f"  {'─'*2} {'─'*12} {'─'*10} {'─'*8}  {'─'*24}")
    for a in audit:
        detalhe = a["error"][:60] if a["error"] else ""
        print(f"  {a['icon']:2s} {a['src']:<12} {a['rows']:>10,} {a['seconds']:>7.1f}s  {detalhe}")
    print(f"{'═'*64}")
    print("  Detalhe completo persistido em ops.ingestion_runs (use: ingestion freshness)")
    print(f"{'═'*64}\n")
    return 1 if falhas else 0


def cmd_freshness() -> int:
    rows = IngestionState().freshness()
    print("\n═══ Saúde das Fontes — última execução por entidade ═══\n")
    if not rows:
        print("  (sem execuções registradas em ops.ingestion_runs)\n")
        return 0
    print(f"  {'Fonte':<10} {'Entidade':<14} {'Status':<8} {'Linhas':>9}  {'Watermark (dado)':<26} {'Última carga (UTC)'}")
    print(f"  {'─'*10} {'─'*14} {'─'*8} {'─'*9}  {'─'*26} {'─'*22}")
    for r in rows:
        we = r.get("max_event_at"); fin = r.get("finished_at")
        print(f"  {r['source']:<10} {r['entity']:<14} {r['status']:<8} {(r.get('rows_loaded') or 0):>9,}  "
              f"{str(we) if we else '—':<26} {str(fin) if fin else '—'}")
    print()
    return 0


# ── Parser ───────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingestion", description="Framework de ingestão multi-fonte → BigQuery")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="Executa a ingestão de uma fonte")
    p_ing.add_argument("--source", required=True)
    p_ing.add_argument("--entity", nargs="+", default=None, help="Entidades específicas (default: todas)")
    p_ing.add_argument("--full", action="store_true", help="Ignora watermark (carga cheia)")

    p_test = sub.add_parser("test", help="Testa conexão da fonte")
    p_test.add_argument("--source", required=True)

    p_list = sub.add_parser("list", help="Lista entidades da fonte")
    p_list.add_argument("--source", required=True)

    p_daily = sub.add_parser("daily", help="Roda TODAS as fontes de API (p/ agendador da nuvem)")
    p_daily.add_argument("--exclude", nargs="+", default=None, help="Fontes a pular (ex: miro)")

    sub.add_parser("sources", help="Lista fontes registradas")
    sub.add_parser("freshness", help="Mostra a freshness por fonte/entidade")

    args = parser.parse_args(argv)
    _setup_logging()

    if args.cmd == "ingest":
        return cmd_ingest(args.source, args.entity, args.full)
    if args.cmd == "daily":
        return cmd_daily(args.exclude)
    if args.cmd == "test":
        return cmd_test(args.source)
    if args.cmd == "list":
        return cmd_list(args.source)
    if args.cmd == "sources":
        return cmd_sources()
    if args.cmd == "freshness":
        return cmd_freshness()
    return 2


if __name__ == "__main__":
    sys.exit(main())
