# Pipeline diário (ETL) do Comercial — imagem com o driver ODBC do SQL Server,
# pra alcançar o ERP NSR via pyodbc. Build/deploy no EasyPanel a partir do
# repositório COMPLETO (data_lake_nevoni) — NÃO do data-lake-teste (só dashboard).
#
# Container SEMPRE de pé: roda um cron INTERNO (variável CRON_SCHEDULE) que dispara
# o pipeline todo dia. Sobe como "Aplicativo" no EasyPanel (que mantém de pé).
# Ver docs/easypanel_pipeline.md.
# bookworm (Debian 12) de propósito: o repo ODBC da Microsoft é assinado com SHA1,
# que o trixie (Debian 13, hoje o default do :slim) rejeita ("repository is not signed").
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

# ── Driver ODBC 17 da Microsoft (pyodbc → ERP) + unixODBC ─────────────────────
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
 && dpkg -i packages-microsoft-prod.deb \
 && rm packages-microsoft-prod.deb \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 unixodbc-dev cron \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# dependências primeiro (cache de layer)
COPY requirements-etl.txt .
RUN pip install -r requirements-etl.txt

# código do projeto
COPY . .

# entrypoint: materializa segredos, agenda o cron interno e fica de pé
CMD ["sh", "docker/etl_entrypoint.sh"]
