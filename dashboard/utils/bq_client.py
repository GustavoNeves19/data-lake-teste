"""BigQuery client compartilhado — cacheado para toda a sessão Streamlit."""

import os
import streamlit as st
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


def _find_creds() -> str | None:
    for p in CREDS_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def _creds_from_secrets():
    """Lê service account de st.secrets['gcp_service_account'] (Streamlit Cloud)."""
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
    except Exception:
        pass
    return None


@st.cache_resource(show_spinner=False)
def get_client(project: str = PROJECT_PROD) -> bigquery.Client:
    # 1º) Streamlit Secrets (produção / Streamlit Cloud)
    creds = _creds_from_secrets()
    if creds:
        return bigquery.Client(credentials=creds, project=project)
    # 2º) Arquivo local (desenvolvimento)
    creds_path = _find_creds()
    if creds_path:
        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(credentials=creds, project=project)
    # 3º) Application Default Credentials (gcloud auth)
    return bigquery.Client(project=project)


@st.cache_data(ttl=14400, show_spinner=False)
def query(sql: str, project: str = PROJECT_PROD) -> pd.DataFrame:
    """Executa SQL no BigQuery e cacheia por 4h (a carga do ERP roda ~3x/dia,
    não a cada hora — TTL maior evita cold-cache desnecessário sem mudar valor)."""
    client = get_client(project)
    return client.query(sql).to_dataframe()


@st.cache_data(ttl=3600, show_spinner=False)
def data_ultima_carga(project: str = PROJECT_PROD) -> str:
    """Data/hora (BRT) da última carga do fact_sales_order — frescor REAL dos dados
    de vendas/faturamento. Usar pra exibir 'Dados de ...' em vez da data de hoje."""
    try:
        df = query(
            f"SELECT FORMAT_TIMESTAMP('%d/%m/%Y %Hh%M', MAX(loaded_at), 'America/Sao_Paulo') AS dt "
            f"FROM `{project}.dm_orders.fact_sales_order`",
            project,
        )
        return df["dt"].iloc[0] or "—"
    except Exception:
        return "—"


def gold_not_ready(table: str, msg: str = "") -> None:
    """Exibe card padrão quando uma tabela Gold ainda não existe."""
    import streamlit as st
    default = (
        f"A tabela Gold `{table.split('.')[-1]}` ainda não foi criada. "
        "Construa a transformação Silver → Gold e a tabela aparecerá automaticamente aqui."
    )
    st.info(
        f"**Gold em construção**\n\n{msg or default}\n\n`{table}`",
        icon="",
    )


def query_layer(gold_sql: str, bronze_sql: str, label: str = "") -> tuple[pd.DataFrame, str]:
    """
    Tenta Gold primeiro. Se a tabela não existir, cai para Bronze.

    Retorna (DataFrame, camada_usada) onde camada_usada é "gold" ou "bronze".
    Exibe automaticamente um banner informando qual camada está ativa.
    """
    import streamlit as st
    from google.api_core.exceptions import NotFound, BadRequest

    try:
        df = query(gold_sql)
        return df, "gold"

    except (NotFound, BadRequest, Exception):
        try:
            df = query(bronze_sql)
            return df, "bronze"
        except Exception as e:
            st.error(f"Erro ao consultar Bronze: {e}", icon="")
            return pd.DataFrame(), "error"


def fmt_brl(value: float) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_num(value: float, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".replace(",", ".")


def fmt_pct(value: float) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"
