# Nevoni 360 — container único: o FastAPI serve a API e o build do React na
# mesma origem (sem CORS, um só domínio). Build context = raiz do repo.
# No EasyPanel: Build = Dockerfile, caminho = docker/nevoni360.Dockerfile.

# ---- estágio 1: build do frontend (Vite/React) ----
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# VITE_API_BASE_URL fica vazio de propósito: front e API na mesma origem.
RUN npm run build

# ---- estágio 2: runtime (FastAPI + estáticos) ----
FROM python:3.12-slim
WORKDIR /app

COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/ ./api/
COPY --from=web /web/dist ./web/dist

ENV WEB_DIST=/app/web/dist
ENV PORT=8000
EXPOSE 8000

# Credenciais e chave vêm por variável de ambiente no EasyPanel:
#   GOOGLE_APPLICATION_CREDENTIALS_JSON  (conteúdo do sapient-metrics.json)
#   OPENAI_API_KEY                       (chave do Oráculo)
CMD ["sh", "-c", "python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
