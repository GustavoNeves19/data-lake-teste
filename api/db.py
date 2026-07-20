"""
Camada de banco de dados relacional do backend Nevoni 360.

Centraliza engine SQLAlchemy 2.0, session factory e Base declarativa que
sao consumidos pelos modelos (User, MetaEquipe) e pelas rotas do FastAPI.

Design:
- Le a URL do Postgres em DATABASE_URL.
- Fallback para SQLite local (nevoni_local.db) quando a env nao esta setada,
  util para desenvolvimento em maquina do dev sem Postgres.
- Nao define modelos aqui: apenas engine, SessionLocal, Base e utilitarios.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# Producao usa Postgres (DATABASE_URL setada no EasyPanel).
# Fallback em SQLite local para rodar o backend em dev sem depender de Postgres.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./nevoni_local.db")


def _build_engine(url: str) -> Engine:
    """Cria a engine com opcoes coerentes com o dialeto usado."""
    connect_args: dict = {}
    if url.startswith("sqlite"):
        # SQLite exige check_same_thread=False para uso com FastAPI (threads distintas).
        connect_args["check_same_thread"] = False
        return create_engine(
            url,
            connect_args=connect_args,
            future=True,
        )

    # Postgres (e outros): pool_pre_ping evita conexoes zumbis apos restart do banco.
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
    )


engine: Engine = _build_engine(DATABASE_URL)


# ---------------------------------------------------------------------------
# Session factory + Base declarativa
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)


Base = declarative_base()


# ---------------------------------------------------------------------------
# Dependencia FastAPI + bootstrap de schema
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Dependencia do FastAPI que abre uma sessao por request e garante o close.

    Uso:
        from fastapi import Depends
        from api.db import get_db

        @router.get("/exemplo")
        def exemplo(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Cria as tabelas mapeadas em Base.metadata caso ainda nao existam.

    Idempotente: pode ser chamada em todo startup do FastAPI sem risco.
    Nao executa ALTER TABLE em colunas existentes, apenas CREATE TABLE IF NOT EXISTS
    (comportamento padrao do create_all). Alteracoes de schema exigem migracao
    dedicada.
    """
    # Import tardio evita ciclo: os modelos importam Base deste modulo.
    # Ao chamar init_db a partir do startup do FastAPI, os modulos de modelos
    # ja terao sido importados pela cadeia de imports das rotas.
    Base.metadata.create_all(bind=engine)
