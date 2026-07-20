"""
Teste de ponta a ponta do coletor de Documentos (extract/documents.py) contra
um FTP_TLS simulado em memoria — nao depende do acesso externo ao FTP da
Nevoni. E o item marcado como concluido no checklist da Fase 1: "Teste de
ponta a ponta contra pasta local de mock".

O formato de LIST simulado abaixo e DOS/IIS ("MM-DD-YYYY  HH:MMAM  <DIR>|
tamanho  nome"), confirmado em teste real contra o FTP da Nevoni em
20/07/2026 — a primeira versao deste teste usava formato Unix
("-rw-r--r--...") por engano, o que mascarou um bug real: o parser original
de _walk() so reconhecia Unix e nunca detectava diretorio nem nome completo
no formato DOS (nomes de pasta reais tem espaco no meio, ex. "P.001 -
Elaboracao e Controle de Documentos"), fazendo collect() rodar sem erro mas
devolver 0 arquivos contra o servidor real. Por isso o teste cobre os dois
formatos explicitamente — nunca mais deve haver essa lacuna entre mock e
prod.
"""
from __future__ import annotations

import hashlib
from ftplib import error_perm
from unittest.mock import patch

import pytest

from config.documents import DOCUMENTS_CONFIG, SUPPORTED_EXTENSIONS
from extract.documents import DocumentsFTPExtractor

FAKE_FILES = {
    "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Procedimento/P.001 - Revisao 5.0.pdf": b"conteudo do procedimento oficial",
    "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Anexos/ANEXO 01 - Lista Mestra.xlsx": b"conteudo da lista mestra",
    "Procedimentos/P.044 - Monitoramento/ANEXO 1.doc": b"conteudo legado em .doc",
    "Procedimentos/P.044 - Monitoramento/foto.jpg": b"bytes de uma foto qualquer",
}

# Formato DOS/IIS real — confirmado contra o servidor da Nevoni em 20/07/2026.
FAKE_LISTINGS = {
    "Procedimentos": [
        "07-07-2026  11:16AM       <DIR>          P.001 - Elaboracao e Controle de Documentos",
        "07-07-2026  11:20AM       <DIR>          P.044 - Monitoramento",
    ],
    "Procedimentos/P.001 - Elaboracao e Controle de Documentos": [
        "07-07-2026  11:16AM       <DIR>          Procedimento",
        "07-07-2026  11:16AM       <DIR>          Anexos",
    ],
    "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Procedimento": [
        "07-07-2026  11:17AM            320655 P.001 - Revisao 5.0.pdf",
    ],
    "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Anexos": [
        "07-07-2026  11:18AM             69973 ANEXO 01 - Lista Mestra.xlsx",
    ],
    "Procedimentos/P.044 - Monitoramento": [
        "07-07-2026  11:21AM             60928 ANEXO 1.doc",
        "07-07-2026  11:21AM             45000 foto.jpg",
    ],
    "RH": None,  # simula error_perm ao listar (pasta sem permissao)
}


class FakeFTPTLS:
    """Substitui ftplib.FTP_TLS. Simula a arvore real da Nevoni (Procedimentos
    com subpastas com espaco no nome) sem abrir socket nenhum."""

    def connect(self, host, port, timeout=30):
        pass

    def auth(self):
        pass

    def login(self, user, password):
        pass

    def prot_p(self):
        pass

    def set_pasv(self, flag):
        pass

    def nlst(self):
        return ["Procedimentos", "RH"]

    def retrlines(self, cmd, callback):
        path = cmd.split(" ", 1)[1]
        listing = FAKE_LISTINGS.get(path)
        if listing is None:
            raise error_perm("550 Permission denied")
        for line in listing:
            callback(line)

    def retrbinary(self, cmd, callback):
        path = cmd.split(" ", 1)[1]
        callback(FAKE_FILES[path])

    def quit(self):
        pass


@pytest.fixture(autouse=True)
def _fake_credentials(monkeypatch):
    """DOCUMENTS_CONFIG e um dict mutavel compartilhado por referencia entre
    config.documents e extract.documents — mutar via monkeypatch.setitem
    evita reimportar modulos e restaura o valor original sozinho ao final."""
    monkeypatch.setitem(DOCUMENTS_CONFIG, "host", "mock-host")
    monkeypatch.setitem(DOCUMENTS_CONFIG, "user", "mock-user")
    monkeypatch.setitem(DOCUMENTS_CONFIG, "password", "mock-pass")


def _collect():
    with patch("extract.documents.FTP_TLS", FakeFTPTLS):
        return DocumentsFTPExtractor().collect()


def test_collect_filters_by_extension_and_walks_recursively():
    results = _collect()
    paths = {r.file_path for r in results}

    # Decisao 2 (expandida 13/07): PDF/DOCX/DOC/XLSX entram, imagem avulsa nao.
    # Nomes de pasta com espaco no meio precisam sobreviver inteiros — prova
    # que o parser DOS/IIS nao trunca no primeiro espaco.
    assert paths == {
        "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Procedimento/P.001 - Revisao 5.0.pdf",
        "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Anexos/ANEXO 01 - Lista Mestra.xlsx",
        "Procedimentos/P.044 - Monitoramento/ANEXO 1.doc",
    }
    assert not any(p.endswith("foto.jpg") for p in paths)


def test_collect_computes_correct_sha256_hash_and_metadata():
    results = _collect()
    by_path = {r.file_path: r for r in results}

    doc_path = "Procedimentos/P.001 - Elaboracao e Controle de Documentos/Procedimento/P.001 - Revisao 5.0.pdf"
    procedimento = by_path[doc_path]
    content = FAKE_FILES[doc_path]
    assert procedimento.content_hash == hashlib.sha256(content).hexdigest()
    assert procedimento.file_extension == "pdf"
    assert procedimento.file_size_bytes == len(content)
    assert procedimento.virtual_directory == "Procedimentos"


def test_collect_skips_unlistable_directory_without_crashing():
    # "RH" dispara error_perm no LIST — nao pode derrubar a coleta inteira,
    # so os 3 arquivos suportados de Procedimentos devem voltar.
    results = _collect()
    assert len(results) == 3


def test_extension_filter_rejects_image_files_by_config():
    assert ".jpg" not in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS
    # extensoes legadas pedidas por Frederico na call de 13/07
    assert {".doc", ".xls", ".ppt", ".pptx"}.issubset(SUPPORTED_EXTENSIONS)


def test_missing_host_raises_before_any_connection():
    from config.documents import DOCUMENTS_CONFIG as cfg

    original_host = cfg["host"]
    cfg["host"] = None
    try:
        with pytest.raises(ValueError, match="DOCS_FTP_HOST"):
            DocumentsFTPExtractor()
    finally:
        cfg["host"] = original_host


class TestParseListLine:
    """Cobertura direta do parser de LIST — os dois formatos que o coletor
    pode encontrar. DOS/IIS e o formato real confirmado em producao; Unix e
    mantido por robustez (nao ha garantia de que todo FTP que a Nevoni venha
    a expor no futuro seja IIS)."""

    def test_dos_iis_directory_with_spaces_in_name(self):
        name, is_dir = DocumentsFTPExtractor._parse_list_line(
            "07-07-2026  11:16AM       <DIR>          P.001 - Elaboracao e Controle de Documentos"
        )
        assert is_dir is True
        assert name == "P.001 - Elaboracao e Controle de Documentos"

    def test_dos_iis_file_with_spaces_in_name(self):
        name, is_dir = DocumentsFTPExtractor._parse_list_line(
            "07-07-2026  11:17AM            320655 P.001 - Revisao 5.0.pdf"
        )
        assert is_dir is False
        assert name == "P.001 - Revisao 5.0.pdf"

    def test_unix_directory(self):
        name, is_dir = DocumentsFTPExtractor._parse_list_line(
            "drwxr-xr-x   2 owner group      4096 Jan 01 00:00 Subpasta"
        )
        assert is_dir is True
        assert name == "Subpasta"

    def test_unix_file(self):
        name, is_dir = DocumentsFTPExtractor._parse_list_line(
            "-rw-r--r--   1 owner group      1234 Jan 01 00:00 relatorio.pdf"
        )
        assert is_dir is False
        assert name == "relatorio.pdf"

    def test_blank_line_returns_none(self):
        assert DocumentsFTPExtractor._parse_list_line("") is None
        assert DocumentsFTPExtractor._parse_list_line("   ") is None
