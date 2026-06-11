"""
Cliente BigQuery do backend Comercial.

Espelha dashboard/utils/bq_client.py (mesma lógica de credenciais e mesmo cache
de 1h), mas sem dependência do Streamlit — para rodar dentro do FastAPI.
Custo de BigQuery é idêntico ao dashboard atual: cache TTL de 1h por SQL.
"""

import os
import time
import threading

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_PROD = "sapient-metrics-492914-m7"   # Nevoni produção
PROJECT_TEST = "vanguardia-prod-466114"        # Vanguard teste

CREDS_PATHS = [
    r"C:\teste\sapient-metrics.json",      # Nevoni produção (principal)
    r"C:\teste\credentials.json",
    r"C:\teste\nevoni-credentials.json",
    r"C:\teste\service-account.json",
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
]

_client: bigquery.Client | None = None
_client_lock = threading.Lock()

# Cache em memória — espelha o @st.cache_data(ttl=3600) do Streamlit.
_cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 3600  # segundos


def _find_creds() -> str | None:
    for p in CREDS_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def get_client(project: str = PROJECT_PROD) -> bigquery.Client:
    global _client
    with _client_lock:
        if _client is None:
            creds_path = _find_creds()
            if creds_path:
                creds = service_account.Credentials.from_service_account_file(
                    creds_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                _client = bigquery.Client(credentials=creds, project=project)
            else:
                # Application Default Credentials (gcloud auth)
                _client = bigquery.Client(project=project)
        return _client


def query(sql: str, project: str = PROJECT_PROD) -> pd.DataFrame:
    """Executa SQL no BigQuery com cache TTL de 1h por (sql, project)."""
    key = (sql, project)
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    df = get_client(project).query(sql).to_dataframe()
    with _cache_lock:
        _cache[key] = (now, df)
    return df
