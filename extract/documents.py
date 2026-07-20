"""
Coletor de documentos via FTPS — servidor fisico da Nevoni (IIS).

ftplib.FTP puro e PROIBIDO neste modulo (Decisao 7 do PIPELINE_DOCUMENTOS_FTP.md)
— toda conexao passa por FTP_TLS, canal de controle e de dados criptografados
(prot_p()). Modo sempre passivo (Decisao 8) — nao existe caminho de codigo pra
modo ativo.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from ftplib import FTP_TLS, error_perm

import structlog

from config.documents import DOCUMENTS_CONFIG, SUPPORTED_EXTENSIONS

logger = structlog.get_logger(__name__)


@dataclass
class RemoteFile:
    virtual_directory: str
    file_path: str
    file_name: str
    file_extension: str
    file_size_bytes: int
    content: bytes
    content_hash: str
    source_modified_at: datetime | None


class DocumentsFTPExtractor:
    """Pre-requisito: DOCS_FTP_HOST/PORT/USER/PASSWORD no .env."""

    def __init__(self):
        self._cfg = DOCUMENTS_CONFIG
        if not self._cfg["host"]:
            raise ValueError(
                "DOCS_FTP_HOST nao configurado no .env. "
                "Configure as credenciais antes de rodar o coletor."
            )

    def _connect(self) -> FTP_TLS:
        ftp = FTP_TLS()
        # O IIS FTP da Nevoni responde LIST/nomes de arquivo em cp1252, nao
        # UTF-8 (confirmado em teste real 20/07/2026 — nome de arquivo com
        # acento quebrava com UnicodeDecodeError no default 'utf-8' do
        # ftplib). cp1252 e superset de latin-1 pros bytes que o Windows usa;
        # setar antes de connect() pra valer em toda troca de texto (USER,
        # LIST, nomes de arquivo).
        ftp.encoding = "cp1252"
        ftp.connect(self._cfg["host"], self._cfg["port"], timeout=30)
        ftp.auth()           # AUTH TLS — canal de controle criptografado
        ftp.login(self._cfg["user"], self._cfg["password"])
        ftp.prot_p()          # PROT P — criptografa TAMBEM o canal de dados; sem
                               # isso o FTPS protegeria so login/senha e o
                               # conteudo do arquivo trafegaria em claro (FTPS
                               # "pela metade", inaceitavel pela Decisao 7).
        ftp.set_pasv(True)    # trava modo passivo — Decisao 8
        logger.info("docs_ftp_connected", host=self._cfg["host"])
        return ftp

    @staticmethod
    def _parse_list_line(line: str) -> "tuple[str, bool] | None":
        """Interpreta uma linha de LIST em formato Unix ou DOS/IIS. Confirmado
        em teste real 20/07/2026: o IIS da Nevoni responde em formato DOS
        ('MM-DD-YYYY  HH:MMAM  <DIR>|tamanho  nome'), NAO Unix
        ('-rw-r--r--  1 owner group  1234 Jan 01 00:00 nome') — os dois
        formatos tem nome de arquivo/pasta com espaco no meio (ex.: 'P.001 -
        Elaboracao e Controle de Documentos'), entao o parser precisa
        preservar tudo depois do 3o/4o campo fixo, nao so pegar a ultima
        palavra."""
        line = line.rstrip("\r\n")
        if not line.strip():
            return None
        if line[0].isdigit():
            # DOS/IIS: data sempre comeca com digito (07-07-2026...).
            parts = line.split(None, 3)
            if len(parts) < 4:
                return None
            return parts[3], parts[2] == "<DIR>"
        # Unix: primeiro char eh o tipo (d=dir, -=arquivo, l=link).
        parts = line.split(None, 8)
        if len(parts) < 9:
            return None
        return parts[8], line.startswith("d")

    def _walk(self, ftp: FTP_TLS, path: str) -> list[str]:
        """Percorre recursivamente um diretorio virtual. Retorna caminhos
        completos de arquivo (subpastas so sao usadas pra descer, nunca
        aparecem na lista de retorno)."""
        files: list[str] = []
        try:
            listing: list[str] = []
            ftp.retrlines(f"LIST {path}", listing.append)
        except error_perm as e:
            # Diretorio sem permissao de listagem ou vazio — nao derruba o
            # coletor inteiro por causa de UMA pasta problematica.
            logger.warning("docs_ftp_list_error", path=path, error=str(e))
            return files

        for line in listing:
            parsed = self._parse_list_line(line)
            if parsed is None:
                continue
            name, is_dir = parsed
            if name in (".", ".."):
                continue
            full_path = f"{path.rstrip('/')}/{name}"
            files.extend(self._walk(ftp, full_path) if is_dir else [full_path])
        return files

    def _download(self, ftp: FTP_TLS, file_path: str) -> bytes:
        buffer = io.BytesIO()
        ftp.retrbinary(f"RETR {file_path}", buffer.write)
        return buffer.getvalue()

    def collect(self) -> list[RemoteFile]:
        """
        Conecta, percorre todos os diretorios virtuais expostos na raiz, baixa
        cada arquivo com extensao suportada (Decisao 2) e calcula o hash
        SHA-256 (Decisao 4). Extensao fora do escopo e ignorada silenciosamente
        — nao e erro, so nao vira linha no catalogo.
        """
        ftp = self._connect()
        results: list[RemoteFile] = []
        try:
            virtual_directories = ftp.nlst()
            logger.info("docs_ftp_root_listing", total=len(virtual_directories))

            for vdir in virtual_directories:
                for file_path in self._walk(ftp, vdir):
                    ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
                    if ext not in SUPPORTED_EXTENSIONS:
                        continue  # imagem avulsa etc. — Decisao 2

                    content = self._download(ftp, file_path)
                    results.append(RemoteFile(
                        virtual_directory=vdir,
                        file_path=file_path,
                        file_name=file_path.rsplit("/", 1)[-1],
                        file_extension=ext.lstrip("."),
                        file_size_bytes=len(content),
                        content=content,
                        content_hash=hashlib.sha256(content).hexdigest(),
                        source_modified_at=None,  # MDTM opcional — nem todo IIS
                                                    # responde; nao bloqueia, o
                                                    # content_hash ja resolve
                                                    # deteccao de mudanca.
                    ))
            logger.info("docs_ftp_collect_done", total_files=len(results))
        finally:
            ftp.quit()  # sempre fecha a sessao, mesmo se um arquivo falhar
        return results
