"""
Admin CRUD — gestão de usuários da Nevoni 360.

Todas as rotas exigem is_admin (Depends(require_admin) de api.auth). Retorna
sempre users sem senha_hash. Soft-delete (is_active=False) em vez de DELETE
físico. Protege contra rebaixar/desativar o último admin ativo do sistema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .auth import (
    User,
    hash_password,
    nome_publico_usuario,
    normalizar_paginas_liberadas,
    normalizar_paginas_ocultas,
    normalizar_recursos_liberados,
    normalizar_recursos_ocultos,
    paginas_liberadas_por_ocultas,
    recursos_liberados_por_ocultos,
    require_admin,
)
from .db import SessionLocal


router = APIRouter(prefix="/api/admin", tags=["admin"])

DEFAULT_HIDDEN_PAGES = [
    "/visao-geral",
    "/comercial",
    "/compras",
    "/financeiro",
    "/price",
    "/operacional",
    "/sac",
    "/engenharia",
    "/juridico",
    "/oraculo",
]

DEFAULT_HIDDEN_RESOURCES = [
    "comercial:vendas",
    "comercial:gestao-vista",
    "comercial:rfv",
    "comercial:performance",
    "financeiro:kpis",
    "financeiro:dre",
    "financeiro:contas-receber",
    "financeiro:contas-pagar",
    "financeiro:liquidacoes",
    "financeiro:fluxo-caixa",
    "sac:atendimentos",
    "sac:sla",
    "sac:chamadas",
    "sac:chat",
    "operacional:producao",
    "operacional:estoque",
    "operacional:bom",
    "engenharia:catalogo",
    "engenharia:bom",
    "engenharia:roadmap",
]


# ── Schemas ─────────────────────────────────────────────────────────────


class UserOut(BaseModel):
    id: int
    email: str
    nome: str
    is_admin: bool
    pode_editar_metas: bool
    pode_usar_oraculo: bool
    paginas_ocultas: list[str] = Field(default_factory=list)
    recursos_ocultos: list[str] = Field(default_factory=list)
    paginas_liberadas: list[str] | None = None
    recursos_liberados: list[str] | None = None
    is_active: bool
    precisa_trocar_senha: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: str
    nome: str = Field(..., min_length=1)
    senha_inicial: str = Field(..., min_length=6)
    is_admin: bool = False
    pode_editar_metas: bool = False
    pode_usar_oraculo: bool = False
    paginas_ocultas: list[str] = Field(default_factory=lambda: list(DEFAULT_HIDDEN_PAGES))
    recursos_ocultos: list[str] = Field(default_factory=lambda: list(DEFAULT_HIDDEN_RESOURCES))
    paginas_liberadas: list[str] | None = None
    recursos_liberados: list[str] | None = None


class ResetSenha(BaseModel):
    nova_senha: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=1)
    is_admin: Optional[bool] = None
    pode_editar_metas: Optional[bool] = None
    pode_usar_oraculo: Optional[bool] = None
    paginas_ocultas: Optional[list[str]] = None
    recursos_ocultos: Optional[list[str]] = None
    paginas_liberadas: Optional[list[str]] = None
    recursos_liberados: Optional[list[str]] = None
    is_active: Optional[bool] = None
    resetar_senha: Optional[ResetSenha] = None


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        nome=nome_publico_usuario(u),
        is_admin=bool(u.is_admin),
        pode_editar_metas=bool(u.pode_editar_metas),
        pode_usar_oraculo=bool(u.pode_usar_oraculo),
        paginas_ocultas=normalizar_paginas_ocultas(getattr(u, "paginas_ocultas", [])),
        recursos_ocultos=normalizar_recursos_ocultos(getattr(u, "recursos_ocultos", [])),
        paginas_liberadas=normalizar_paginas_liberadas(getattr(u, "paginas_liberadas", None))
        if isinstance(getattr(u, "paginas_liberadas", None), list) else None,
        recursos_liberados=normalizar_recursos_liberados(getattr(u, "recursos_liberados", None))
        if isinstance(getattr(u, "recursos_liberados", None), list) else None,
        is_active=bool(u.is_active),
        precisa_trocar_senha=bool(u.precisa_trocar_senha),
        created_at=getattr(u, "created_at", None),
        last_login_at=getattr(u, "last_login_at", None),
    )


def _count_admins_ativos(db: Session, excluir_id: Optional[int] = None) -> int:
    """Conta administradores ativos, opcionalmente ignorando um id."""
    query = db.query(User).filter(User.is_admin.is_(True), User.is_active.is_(True))
    if excluir_id is not None:
        query = query.filter(User.id != excluir_id)
    return query.count()


# ── Rotas ───────────────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserOut])
def listar_users(_: User = Depends(require_admin)) -> list[UserOut]:
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id.asc()).all()
        return [_to_out(u) for u in users]
    finally:
        db.close()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def criar_user(payload: UserCreate, _: User = Depends(require_admin)) -> UserOut:
    db = SessionLocal()
    try:
        email_norm = payload.email.strip().lower()
        existente = db.query(User).filter(User.email == email_norm).first()
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um usuário com este e-mail.",
            )

        novo = User(
            email=email_norm,
            nome=payload.nome.strip(),
            senha_hash=hash_password(payload.senha_inicial),
            is_admin=bool(payload.is_admin),
            pode_editar_metas=bool(payload.pode_editar_metas),
            pode_usar_oraculo=bool(payload.pode_usar_oraculo),
            paginas_ocultas=normalizar_paginas_ocultas(payload.paginas_ocultas),
            recursos_ocultos=normalizar_recursos_ocultos(payload.recursos_ocultos),
            paginas_liberadas=normalizar_paginas_liberadas(payload.paginas_liberadas)
            if payload.paginas_liberadas is not None else paginas_liberadas_por_ocultas(payload.paginas_ocultas),
            recursos_liberados=normalizar_recursos_liberados(payload.recursos_liberados)
            if payload.recursos_liberados is not None else recursos_liberados_por_ocultos(payload.recursos_ocultos),
            is_active=True,
            precisa_trocar_senha=True,
        )
        db.add(novo)
        db.commit()
        db.refresh(novo)
        return _to_out(novo)
    finally:
        db.close()


@router.patch("/users/{user_id}", response_model=UserOut)
def atualizar_user(
    user_id: int,
    payload: UserUpdate,
    _: User = Depends(require_admin),
) -> UserOut:
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if u is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado.",
            )

        # Protege: não pode rebaixar o último admin ativo.
        if payload.is_admin is False and bool(u.is_admin):
            if _count_admins_ativos(db, excluir_id=u.id) == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Não é possível rebaixar o último administrador ativo.",
                )

        # Protege: não pode desativar o último admin ativo.
        if payload.is_active is False and bool(u.is_admin) and bool(u.is_active):
            if _count_admins_ativos(db, excluir_id=u.id) == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Não é possível desativar o último administrador ativo.",
                )

        if payload.nome is not None:
            u.nome = payload.nome.strip()
        if payload.is_admin is not None:
            u.is_admin = bool(payload.is_admin)
        if payload.pode_editar_metas is not None:
            u.pode_editar_metas = bool(payload.pode_editar_metas)
        if payload.pode_usar_oraculo is not None:
            u.pode_usar_oraculo = bool(payload.pode_usar_oraculo)
        if payload.paginas_ocultas is not None:
            u.paginas_ocultas = normalizar_paginas_ocultas(payload.paginas_ocultas)
        if payload.recursos_ocultos is not None:
            u.recursos_ocultos = normalizar_recursos_ocultos(payload.recursos_ocultos)
        if payload.paginas_liberadas is not None:
            u.paginas_liberadas = normalizar_paginas_liberadas(payload.paginas_liberadas)
        elif payload.paginas_ocultas is not None:
            u.paginas_liberadas = paginas_liberadas_por_ocultas(payload.paginas_ocultas)
        if payload.recursos_liberados is not None:
            u.recursos_liberados = normalizar_recursos_liberados(payload.recursos_liberados)
        elif payload.recursos_ocultos is not None:
            u.recursos_liberados = recursos_liberados_por_ocultos(payload.recursos_ocultos)
        if payload.is_active is not None:
            u.is_active = bool(payload.is_active)
        if payload.resetar_senha is not None:
            u.senha_hash = hash_password(payload.resetar_senha.nova_senha)
            u.precisa_trocar_senha = True

        db.commit()
        db.refresh(u)
        return _to_out(u)
    finally:
        db.close()


@router.delete("/users/{user_id}", response_model=UserOut)
def desativar_user(
    user_id: int,
    _: User = Depends(require_admin),
) -> UserOut:
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if u is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado.",
            )

        if bool(u.is_admin) and bool(u.is_active):
            if _count_admins_ativos(db, excluir_id=u.id) == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Não é possível desativar o último administrador ativo.",
                )

        u.is_active = False
        db.commit()
        db.refresh(u)
        return _to_out(u)
    finally:
        db.close()
