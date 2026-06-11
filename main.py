

import argparse
import sys
import json
import structlog

from config.settings import (
    LOG_LEVEL, ENVIRONMENT, DOMAIN_LOAD_ORDER, ENTITIES,
    get_all_entities_ordered,
)
from orchestration.pipeline import ETLPipeline


# ── Configuração de logging

def setup_logging():
    """Configura structlog com output JSON em prod, colorido em dev."""
    processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if ENVIRONMENT == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ── Comandos

def cmd_test():
    """Testa conexões SQL Server e BigQuery."""
    pipeline = ETLPipeline()
    logger = structlog.get_logger()

    print("\n═══ Teste de Conexão — SQL Server (ERP) ═══")
    try:
        info = pipeline.extractor.test_connection()
        print(f"  ✓ Conectado: {info['database']} ({info['user']})")
        print(f"  ✓ Versão: {info['version'][:80]}...")
        print(f"  ✓ Hora do servidor: {info['server_time']}")
        pipeline.extractor.disconnect()
    except Exception as e:
        print(f"  ✗ ERRO: {e}")

    print("\n═══ Teste de Conexão — BigQuery (DW) ═══")
    try:
        pipeline.loader.connect()
        pipeline.loader.ensure_dataset()
        print(f"  ✓ Conectado ao projeto")
        print(f"  ✓ Dataset pronto")
        pipeline.loader.disconnect()
    except Exception as e:
        print(f"  ✗ ERRO: {e}")

    print()


def cmd_list():
    """Lista todas as entidades por domínio."""
    print("\n═══ Entidades do Pipeline ETL ═══\n")
    total = 0
    for domain in DOMAIN_LOAD_ORDER:
        entities = [
            (n, c) for n, c in ENTITIES.items() if c["domain"] == domain
        ]
        entities.sort(key=lambda x: x[1]["load_order"])
        print(f"  {domain} ({len(entities)} entidades)")
        for name, cfg in entities:
            etype = cfg["entity_type"]
            cols = len(cfg["bq_schema"])
            print(f"    {cfg['load_order']}. {name:<35} [{etype:<8}] {cols} colunas")
            total += 1
        print()
    print(f"  Total: {total} entidades em {len(DOMAIN_LOAD_ORDER)} domínios\n")


def cmd_create_tables():
    """Cria todas as tabelas no BigQuery sem carregar dados."""
    pipeline = ETLPipeline()
    entities = get_all_entities_ordered()
    print(f"\nCriando {len(entities)} tabelas no BigQuery...\n")
    table_map = pipeline.loader.create_all_tables(entities)
    for name, tid in table_map.items():
        print(f"  ✓ {tid}")
    pipeline.loader.disconnect()
    print(f"\n{len(table_map)} tabelas criadas.\n")


def cmd_validate():
    """Valida contagem de linhas de todas as tabelas."""
    pipeline = ETLPipeline()
    results = pipeline.validate_all()
    print("\n═══ Validação de Carga ═══\n")
    print(f"  {'Entidade':<35} {'Domínio':<12} {'Linhas':>10}")
    print(f"  {'─'*35} {'─'*12} {'─'*10}")
    total = 0
    for r in results:
        rows = r["rows"] if r["rows"] >= 0 else "N/A"
        print(f"  {r['entity']:<35} {r['domain']:<12} {rows:>10}")
        if isinstance(rows, int):
            total += rows
    print(f"\n  Total de linhas: {total:,}\n")


def cmd_run(domains=None, entities_filter=None):
    """Executa o pipeline ETL."""
    pipeline = ETLPipeline()

    scope = "completo"
    if domains:
        scope = f"domínios: {', '.join(domains)}"
    elif entities_filter:
        scope = f"entidades: {', '.join(entities_filter)}"

    print(f"\n═══ Pipeline ETL — {scope} ═══\n")

    result = pipeline.run_full(domains=domains, entities_filter=entities_filter)

    # Resumo
    print(f"\n{'═'*60}")
    print(f"  Pipeline concluído em {result.total_seconds}s")
    print(f"  ✓ OK: {result.entities_ok}  ✗ Erro: {result.entities_error}  ⊘ Vazio: {result.entities_skipped}")
    print(f"  Total de linhas carregadas: {result.total_rows:,}")
    print(f"{'═'*60}\n")

    # Detalhes
    if result.details:
        print(f"  {'Entidade':<35} {'Status':<8} {'Extraído':>10} {'Carregado':>10} {'Tempo':>7}")
        print(f"  {'─'*35} {'─'*8} {'─'*10} {'─'*10} {'─'*7}")
        for d in result.details:
            status_icon = "✓" if d.status == "ok" else ("✗" if d.status == "error" else "⊘")
            print(
                f"  {d.entity:<35} {status_icon} {d.status:<6} "
                f"{d.rows_extracted:>10,} {d.rows_loaded:>10,} {d.seconds:>6.1f}s"
            )
        print()

    # Erros
    errors = [d for d in result.details if d.status == "error"]
    if errors:
        print("  ⚠ Entidades com erro:")
        for e in errors:
            print(f"    • {e.entity}: {e.error}")
        print()

    return 0 if result.entities_error == 0 else 1


# ── CLI 

def main():
    parser = argparse.ArgumentParser(
        description="ETL Pipeline — SQL Server (ERP) → BigQuery (DW)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test", action="store_true", help="Testar conexões")
    parser.add_argument("--list", action="store_true", help="Listar entidades")
    parser.add_argument("--create-tables", action="store_true", help="Criar tabelas no BQ")
    parser.add_argument("--validate", action="store_true", help="Validar contagem pós-carga")
    parser.add_argument("--domain", type=str, nargs="+", help="Processar domínio(s) específico(s)")
    parser.add_argument("--entity", type=str, nargs="+", help="Processar entidade(s) específica(s)")

    args = parser.parse_args()

    setup_logging()

    if args.test:
        cmd_test()
    elif args.list:
        cmd_list()
    elif args.create_tables:
        cmd_create_tables()
    elif args.validate:
        cmd_validate()
    else:
        domains = [d.upper() for d in args.domain] if args.domain else None
        entities = args.entity if args.entity else None
        exit_code = cmd_run(domains=domains, entities_filter=entities)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
