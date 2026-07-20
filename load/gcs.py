"""
Upload dos documentos originais para o cofre (Google Cloud Storage).
So grava o byte a byte fiel ao FTP — nunca processa/transforma conteudo (essa
e a fronteira entre cofre e bronze/silver, ver Decisao 3 do
PIPELINE_DOCUMENTOS_FTP.md). Reusa a mesma GOOGLE_APPLICATION_CREDENTIALS ja
usada pelo BigQueryLoader — mesmo projeto GCP, credencial unica.
"""
from __future__ import annotations

import structlog
from google.cloud import storage

from config.documents import DOCUMENTS_CONFIG

logger = structlog.get_logger(__name__)


class DocumentsGCSLoader:
    def __init__(self):
        self._client = storage.Client()
        self._bucket = self._client.bucket(DOCUMENTS_CONFIG["gcs_bucket"])

    def upload(self, file_path: str, content: bytes, content_hash: str) -> str:
        """
        Nome do objeto inclui o content_hash — se o conteudo nao mudou desde a
        ultima carga, o objeto ja existe e o upload e pulado (idempotente, sem
        custo de rede/armazenamento duplicado). Se o conteudo mudou, o hash
        muda e o novo objeto convive com o antigo — nada e sobrescrito, o
        cofre acumula versoes por natureza do esquema de nomes, sem precisar
        de GCS Object Versioning.
        """
        blob_name = f"{file_path.lstrip('/')}/{content_hash}"
        blob = self._bucket.blob(blob_name)
        if not blob.exists():
            blob.upload_from_string(content)
            logger.info("gcs_upload_ok", blob=blob_name, bytes=len(content))
        else:
            logger.debug("gcs_upload_skip_exists", blob=blob_name)
        return f"gs://{DOCUMENTS_CONFIG['gcs_bucket']}/{blob_name}"
