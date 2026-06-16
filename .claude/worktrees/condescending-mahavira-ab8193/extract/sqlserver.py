"""
Módulo de extração — SQL Server (ERP).
Lê queries .sql e retorna DataFrames via pyodbc + pandas.
"""

import time

import pandas as pd
import pyodbc
import structlog

from config.settings import (
    SQL_SERVER_CONFIG,
    QUERIES_DIR,
    MAX_RETRIES,
    RETRY_DELAY,
    BATCH_SIZE,
    QUERY_TIMEOUT_SECONDS,
    LOCK_TIMEOUT_MS,
)

logger = structlog.get_logger(__name__)


class SQLServerExtractor:
    """Extrai dados do SQL Server (ERP) usando queries SQL pré-definidas."""

    def __init__(self):
        self._conn = None

    # ── Conexão

    @property
    def _connection_string(self) -> str:
        cfg = SQL_SERVER_CONFIG
        return (
            f"DRIVER={{{cfg['driver']}}};"
            f"SERVER={cfg['server']},{cfg['port']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['uid']};"
            f"PWD={cfg['pwd']};"
            "TrustServerCertificate=yes;"
            "Connection Timeout=30;"
        )

    def connect(self) -> None:
        """Abre conexão com o SQL Server."""
        if self._conn:
            return

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._conn = pyodbc.connect(self._connection_string, readonly=True)
                logger.info(
                    "sqlserver_connected",
                    server=SQL_SERVER_CONFIG["server"],
                    database=SQL_SERVER_CONFIG["database"],
                )
                return
            except pyodbc.Error as e:
                logger.warning("sqlserver_connect_retry", attempt=attempt, error=str(e))
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    raise ConnectionError(
                        f"Falha ao conectar no SQL Server após {MAX_RETRIES} tentativas: {e}"
                    )

    def disconnect(self) -> None:
        """Fecha conexão."""
        if self._conn:
            try:
                self._conn.close()
            except pyodbc.Error:
                pass
            self._conn = None
            logger.info("sqlserver_disconnected")

    def is_connected(self) -> bool:
        """Verifica se a conexão está ativa."""
        if not self._conn:
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except pyodbc.Error:
            self._conn = None
            return False

    # ── Extração

    def _load_query(self, query_file: str) -> str:
        """Carrega SQL de arquivo."""
        filepath = QUERIES_DIR / query_file
        if not filepath.exists():
            raise FileNotFoundError(f"Query não encontrada: {filepath}")
        return filepath.read_text(encoding="utf-8").strip()

    def extract_entity(self, entity_name: str, query_file: str) -> pd.DataFrame:
        """
        Extrai uma entidade do ERP e retorna como DataFrame.
        Usa server-side cursor com fetchmany para controle de memória
        e log de progresso a cada BATCH_SIZE linhas.

        Args:
            entity_name: Nome da entidade (ex: 'dim_company')
            query_file:  Nome do arquivo SQL (ex: 'dim_company.sql')

        Returns:
            DataFrame com dados extraídos, colunas já renomeadas pelo AS.
        """
        if not self.is_connected():
            self.connect()

        sql = self._load_query(query_file)
        start = time.time()

        try:
            cursor = self._conn.cursor()

            # # Timeout no lado do cliente (em segundos)
            # cursor.timeout = QUERY_TIMEOUT_SECONDS

            # Timeout de lock no SQL Server (em milissegundos)
            cursor.execute(f"SET LOCK_TIMEOUT {LOCK_TIMEOUT_MS}")
            cursor.execute(sql)

            columns = [desc[0] for desc in cursor.description]
            chunks: list[pd.DataFrame] = []
            fetched = 0

            while True:
                batch = cursor.fetchmany(BATCH_SIZE)
                if not batch:
                    break
                chunks.append(pd.DataFrame.from_records(batch, columns=columns))
                fetched += len(batch)
                logger.debug(
                    "extract_progress",
                    entity=entity_name,
                    rows_fetched=fetched,
                )

            cursor.close()

            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)
            elapsed = round(time.time() - start, 2)

            logger.info(
                "extract_ok",
                entity=entity_name,
                rows=len(df),
                cols=len(df.columns),
                seconds=elapsed,
            )
            return df

        except (pyodbc.Error, pd.errors.DatabaseError) as e:
            logger.error("extract_error", entity=entity_name, error=str(e))
            self.disconnect()
            raise

    def test_connection(self) -> dict:
        """Testa conexão e retorna info do servidor."""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        cursor.execute("SELECT DB_NAME(), SUSER_NAME(), GETDATE()")
        db, user, now = cursor.fetchone()
        cursor.close()
        return {"version": version, "database": db, "user": user, "server_time": str(now)}

    # ── Context Manager

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
