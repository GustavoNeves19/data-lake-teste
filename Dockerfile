FROM python:3.12-slim

WORKDIR /app

# Copia dependências primeiro (cache de layers)
COPY requirements.txt dashboard/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r dashboard/requirements.txt

# Copia todo o projeto
COPY . .

# Streamlit config via variáveis de ambiente
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# BigQuery credentials montadas via secret no Cloud Run
ENV GOOGLE_APPLICATION_CREDENTIALS=/secrets/credentials.json

EXPOSE 8080

CMD ["python", "-m", "streamlit", "run", "dashboard/app.py", \
     "--server.port=8080", "--server.address=0.0.0.0"]
