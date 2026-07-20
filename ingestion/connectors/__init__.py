"""
Factory de conectores. Mapeia o nome declarado em config/sources/<source>.json
(`connector`) para a classe que o implementa.

Adicionar fonte = registrar uma linha aqui + a classe. Import preguiçoso para
não exigir as deps de todas as fontes numa execução de fonte única.
"""

from __future__ import annotations

from ingestion.connectors.base import SourceConnector

_REGISTRY = {
    "umbler":    ("ingestion.connectors.umbler", "UmblerConnector"),
    "pipedrive": ("ingestion.connectors.pipedrive", "PipedriveConnector"),
    "gmail":     ("ingestion.connectors.gmail", "GmailConnector"),
    "clickup":   ("ingestion.connectors.clickup", "ClickUpConnector"),
    "miro":      ("ingestion.connectors.miro", "MiroConnector"),
    # "goto":      ("ingestion.connectors.goto", "GoToConnector"),
}


def get_connector(name: str) -> SourceConnector:
    if name not in _REGISTRY:
        disponiveis = ", ".join(sorted(_REGISTRY)) or "(nenhum)"
        raise ValueError(f"Conector '{name}' não registrado. Disponíveis: {disponiveis}")
    module_path, class_name = _REGISTRY[name]
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()
