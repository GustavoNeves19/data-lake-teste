"""
Diagnóstico de encoding — roda ANTES e DEPOIS das correções.

Uso:
    python -m transform.encoding_diagnostic

Conecta no SQL Server, analisa colunas string de todas as tabelas
e gera relatório de quantos registros têm "?" por coluna.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyodbc
import structlog
from config.settings import SQL_SERVER_CONFIG

logger = structlog.get_logger(__name__)

# Tabelas e colunas a verificar (as mais afetadas)
COLUMNS_TO_CHECK = {
    "ITENS": ["YNOMITM", "YDISITM"],
    "[CLIENTES OU FORNECEDORES]": ["YNOMCLI", "YFANCLI", "YCIDCLI", "YBAICLI"],
    "TRANSPORTADORAS": ["YNOMTRA", "YCIDTRA"],
    "[ORÇAMENTOS]": ["YSOLICI", "YOBSERV"],
    "[COMPRAS E VENDAS]": ["YOBSERV", "YOBSPRO", "YSOLICI"],
    "[NATUREZAS DE OPERAÇÕES]": ["YNOMNAT"],
    "[CONDIÇÕES DE PAGAMENTOS]": ["YNOMPGT"],
    "SETORES": ["YNOMSET", "YCIDSET"],
    "[PAGAR E RECEBER]": ["YOBSCOB"],
    "[PROCESSOS IMPORTAÇÕES PEDIDOS]": ["YNOMCLI"],
}


def connect():
    cfg = SQL_SERVER_CONFIG
    conn_str = (
        f"DRIVER={{{cfg['driver']}}};"
        f"SERVER={cfg['server']},{cfg['port']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['uid']};"
        f"PWD={cfg['pwd']};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, readonly=True)


def run_diagnostic():
    print("\n═══ Diagnóstico de Encoding — ERP ═══\n")

    conn = connect()
    cursor = conn.cursor()

    total_affected = 0
    results = []

    for table, columns in COLUMNS_TO_CHECK.items():
        for col in columns:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE '%?%'")
                count = cursor.fetchone()[0]

                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} <> ''")
                total = cursor.fetchone()[0]

                pct = round(count / max(total, 1) * 100, 1)

                status = "✓" if count == 0 else "⚠"
                results.append((table, col, total, count, pct, status))
                total_affected += count

            except Exception as e:
                results.append((table, col, 0, 0, 0, f"✗ ERRO: {e}"))

    # Tabela de resultados
    print(f"  {'Tabela':<40} {'Coluna':<15} {'Total':>8} {'Com ?':>8} {'%':>6}")
    print(f"  {'─'*40} {'─'*15} {'─'*8} {'─'*8} {'─'*6}")

    for table, col, total, count, pct, status in results:
        if count > 0:
            print(f"  {table:<40} {col:<15} {total:>8,} {count:>8,} {pct:>5.1f}%  {status}")

    print(f"\n  Total de registros afetados: {total_affected:,}")

    # Amostra de valores corrompidos das piores colunas
    print(f"\n\n═══ Amostras de Valores Corrompidos ═══\n")

    worst = sorted([r for r in results if r[3] > 0], key=lambda x: x[3], reverse=True)[:5]

    for table, col, total, count, pct, _ in worst:
        cursor.execute(f"SELECT DISTINCT TOP 10 {col} FROM {table} WHERE {col} LIKE '%?%' ORDER BY {col}")
        rows = cursor.fetchall()
        print(f"  {table}.{col} ({count:,} registros):")
        for row in rows:
            print(f"    → {row[0]}")
        print()

    cursor.close()
    conn.close()

    print(f"═══ Diagnóstico concluído ═══\n")
    return total_affected


if __name__ == "__main__":
    run_diagnostic()
