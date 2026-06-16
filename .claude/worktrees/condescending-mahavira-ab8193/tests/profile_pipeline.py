"""
        Profiling do pipeline ETL com line_profiler.

        Decora e executa as funções críticas para uma entidade de teste,
        gerando um relatório linha-a-linha de tempo de execução.

        Uso:
            python tests/profile_pipeline.py [nome_entidade]

        Exemplos:
            python tests/profile_pipeline.py              # usa dim_partner (default)
            python tests/profile_pipeline.py fact_payable

        Resultado salvo em: tests/profile_results.txt
"""
import os
import sys

# Garante que o root do projeto está no path independente de onde o script é chamado
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from line_profiler import LineProfiler

from config.settings import ENTITIES
from extract.sqlserver import SQLServerExtractor
from load.bigquery import BigQueryLoader
from transform.transformations import transform_entity

# Entidade de teste padrão — ~47K linhas, boa representatividade
DEFAULT_ENTITY = "dim_partner"


def main() -> None:
    entity_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ENTITY

    if entity_name not in ENTITIES:
        print(f"[ERRO] Entidade '{entity_name}' não encontrada em ENTITIES.")
        print(f"Disponíveis: {', '.join(ENTITIES.keys())}")
        sys.exit(1)

    entity_config = {"name": entity_name, **ENTITIES[entity_name]}
    print(f"\n=== Profiling: {entity_name} ===")
    print(f"Domain  : {entity_config['domain']}")
    print(f"Query   : {entity_config['query_file']}")
    print(f"BQ table: {entity_config['bq_table']}\n")

    lp = LineProfiler()

    # ── EXTRACT ──────────────────────────────────────────
    with SQLServerExtractor() as extractor:
        profiled_extract = lp(extractor.extract_entity)
        print("Executando extract_entity...")
        df = profiled_extract(entity_name, entity_config["query_file"])
        print(f"  → {len(df):,} linhas extraídas\n")

    # ── TRANSFORM ────────────────────────────────────────
    profiled_transform = lp(transform_entity)
    print("Executando transform_entity...")
    df = profiled_transform(df, entity_name, entity_config)
    print(f"  → {len(df):,} linhas após transform\n")

    # ── LOAD ─────────────────────────────────────────────
    with BigQueryLoader() as loader:
        loader.create_table(entity_config)
        profiled_load = lp(loader.load_dataframe)
        print("Executando load_dataframe...")
        rows_loaded = profiled_load(df, entity_config)
        print(f"  → {rows_loaded:,} linhas carregadas no BigQuery\n")

    # ── Relatório ─────────────────────────────────────────
    results_file = os.path.join(os.path.dirname(__file__), "profile_results.txt")

    with open(results_file, "w", encoding="utf-8") as f:
        f.write(f"Profiling: {entity_name}\n")
        f.write("=" * 70 + "\n\n")
        lp.print_stats(stream=f)

    print("\n" + "=" * 70)
    print("RESULTADO DO PROFILING")
    print("=" * 70)
    lp.print_stats()
    print(f"\nRelatório salvo em: {results_file}")


if __name__ == "__main__":
    main()