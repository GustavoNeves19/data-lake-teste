import pandas as pd
import pyodbc

from config.settings import SQL_SERVER_CONFIG

try:
    connection_string = (
        f"DRIVER={{{SQL_SERVER_CONFIG['driver']}}};"
        f"SERVER={SQL_SERVER_CONFIG['server']},{SQL_SERVER_CONFIG['port']};"
        f"DATABASE={SQL_SERVER_CONFIG['database']};"
        f"UID={SQL_SERVER_CONFIG['uid']};"
        f"PWD={SQL_SERVER_CONFIG['pwd']};"
        "TrustServerCertificate=yes;"
    )

    conn = pyodbc.connect(connection_string)
    print("Conexão com SQL Server realizada com sucesso.\n")

    tables_to_check = {
        "ITENS": ["YNOMITM", "YDISITM"],
        "[CLIENTES OU FORNECEDORES]": ["YNOMCLI", "YFANCLI", "YCIDCLI"],
        "TRANSPORTADORAS": ["YNOMTRA", "YCIDTRA"],
    }

    for table, cols in tables_to_check.items():
        for col in cols:
            query = f"""
                SELECT COUNT(*) AS total
                FROM {table}
                WHERE {col} LIKE '%?%'
            """
            result = pd.read_sql(query, conn)
            count = result.iloc[0]["total"]
            print(f"{table}.{col}: {count} registros com '?'")

    conn.close()

except Exception as e:
    print("Erro ao executar o teste:")
    print(e)