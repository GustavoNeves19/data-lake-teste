from google.cloud import bigquery
from google.api_core.exceptions import Forbidden, NotFound, GoogleAPIError

from config.settings import BQ_PROJECT, BQ_DATASET, BQ_LOCATION


def test_bigquery_insert():
    table_id = f"{BQ_PROJECT}.{BQ_DATASET}.contacts"

    rows_to_insert = [
        {
            "id": 1,
            "name": "Lucas",
            "email": "lucas@teste.com"
        },
        {
            "id": 2,
            "name": "Maria",
            "email": "maria@teste.com"
        }
    ]

    print("=== CONFIGURAÇÃO CARREGADA ===")
    print(f"Projeto : {BQ_PROJECT}")
    print(f"Dataset : {BQ_DATASET}")
    print(f"Location: {BQ_LOCATION}")
    print(f"Tabela  : {table_id}")
    print()

    try:
        client = bigquery.Client(project=BQ_PROJECT)

        print("Cliente BigQuery criado com sucesso.")
        print("Enviando linhas para a tabela...")

        errors = client.insert_rows_json(table_id, rows_to_insert)

        if not errors:
            print("\nCarga enviada com sucesso.")
            print(f"Total de linhas inseridas: {len(rows_to_insert)}")
        else:
            print("\nOcorreram erros na inserção:")
            for error in errors:
                print(error)

    except Forbidden as e:
        print("\nERRO DE PERMISSÃO")
        print("A credencial foi aceita, mas a conta não tem permissão para inserir dados.")
        print(f"Detalhes: {e}")

    except NotFound as e:
        print("\nRECURSO NÃO ENCONTRADO")
        print("Projeto, dataset ou tabela não foram encontrados.")
        print(f"Detalhes: {e}")

    except GoogleAPIError as e:
        print("\nERRO DE API DO GOOGLE")
        print(f"Detalhes: {e}")

    except Exception as e:
        print("\nERRO GERAL")
        print(f"Detalhes: {e}")


if __name__ == "__main__":
    test_bigquery_insert()