"""
Configuracao central do conector de Documentos (FTP Nevoni).
Mesmo padrao de config/umbler.py: credenciais lidas do .env, curadoria de
pastas versionada em JSON — nenhum segredo nem regra de negocio hardcoded.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_CONFIG = {
    "host": os.getenv("DOCS_FTP_HOST"),
    "port": int(os.getenv("DOCS_FTP_PORT", "21")),
    "user": os.getenv("DOCS_FTP_USER"),
    "password": os.getenv("DOCS_FTP_PASSWORD"),
    "use_tls": True,   # travado — Decisao 7 do PIPELINE_DOCUMENTOS_FTP.md. Sem env
                        # var pra desligar: se virasse configuravel, alguem
                        # desligaria "so pra testar" um dia e vazaria pra producao.
    "passive": True,    # travado — Decisao 8, mesmo raciocinio acima.
    "gcs_bucket": os.getenv("DOCS_GCS_BUCKET", "nevoni-datalake-docs"),
    "bq_dataset_bronze": "docs_raw",
    "bq_dataset_silver": "docs_silver",
}

# Escopo de extensoes — Decisao 2 (08/07), expandida em 13/07 a pedido do
# Frederico Oliva (call de revisao tecnica): DOC/XLS (formatos legados,
# mesmo parser de DOCX/XLSX na Fase 2) e PPT/PPTX (extrator python-pptx
# dedicado, ainda nao implementado na Fase 2). Imagem avulsa (.jpg/.png)
# continua fora — nao guarda informacao textual e nao entrou como pedido
# formal do Fred/Diego/Victor.
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}

_FOLDERS_PATH = Path(__file__).resolve().parent / "documents_folders.json"


def load_folder_map() -> dict[str, dict]:
    """Carrega o mapa de curadoria (Decisao 6). Se o arquivo ainda nao existir
    (antes da 1a aprovacao de pastas pelo Fred/Diego), retorna vazio — e vazio,
    combinado com is_official() abaixo, significa 'nada e oficial ainda', que
    e exatamente o comportamento fail-safe desejado."""
    if not _FOLDERS_PATH.exists():
        return {}
    with open(_FOLDERS_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["virtual_directory"]: e for e in entries}


def is_official(virtual_directory: str, folder_map: dict[str, dict]) -> bool:
    """Regra fail-safe travada (Decisao 6): o default e sempre False. So
    retorna True se a entrada existir E is_official estiver explicitamente
    marcado true no JSON — nunca por omissao."""
    entry = folder_map.get(virtual_directory)
    return bool(entry and entry.get("is_official") is True)
