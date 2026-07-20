"""
Módulo de autenticação do backend Nevoni 360.

Concentra:
- Modelo SQLAlchemy `User` (tabela `users`) conforme o contrato global.
- Router FastAPI `/api/auth` com login, logout, me e troca de senha.
- Dependências `get_current_user`, `require_admin` e `require_editar_metas`
  para proteger as demais rotas.
- Rotina `bootstrap_admin` chamada no startup do FastAPI para garantir que
  sempre exista um administrador (ADM master vindo das envs ADMIN_EMAIL /
  ADMIN_PASSWORD).

Regras:
- Cookie de sessão httpOnly (`nevoni_session`) — nunca expor o token em JSON.
- Erros de login retornam 401 genérico. Nenhum detalhe interno vaza.
- Última hora de login é gravada em `last_login_at` a cada login bem-sucedido.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .db import Base, get_db
from .security import (
    COOKIE_NAME,
    clear_session_cookie,
    create_token,
    decode_token,
    hash_password,
    set_session_cookie,
    verify_password,
)
from .access_catalog import PAGINAS_CONTROLADAS, RECURSOS_CONTROLADOS


log = logging.getLogger("nevoni.auth")


def normalizar_paginas_ocultas(value: object) -> list[str]:
    """Mantem apenas rotas de pagina conhecidas, sem duplicar."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item in PAGINAS_CONTROLADAS and item not in out:
            out.append(item)
    return out


def normalizar_paginas_liberadas(value: object) -> list[str]:
    """Mantem apenas rotas conhecidas liberadas explicitamente."""
    return normalizar_paginas_ocultas(value)


def normalizar_recursos_ocultos(value: object) -> list[str]:
    """Mantem apenas abas/recursos conhecidos, sem granularidade de card/coluna."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item in RECURSOS_CONTROLADOS and item not in out:
            out.append(item)
    return out


def normalizar_recursos_liberados(value: object) -> list[str]:
    """Mantem apenas abas/recursos conhecidos liberados explicitamente."""
    return normalizar_recursos_ocultos(value)


def paginas_liberadas_por_ocultas(value: object) -> list[str]:
    ocultas = set(normalizar_paginas_ocultas(value))
    return [pagina for pagina in sorted(PAGINAS_CONTROLADAS) if pagina not in ocultas]


def recursos_liberados_por_ocultos(value: object) -> list[str]:
    ocultos = set(normalizar_recursos_ocultos(value))
    return [recurso for recurso in sorted(RECURSOS_CONTROLADOS) if recurso not in ocultos]


def usuario_pode_acessar_pagina(user: "User", pagina: str) -> bool:
    liberadas = getattr(user, "paginas_liberadas", None)
    if isinstance(liberadas, list):
        return pagina in normalizar_paginas_liberadas(liberadas)
    return pagina not in normalizar_paginas_ocultas(getattr(user, "paginas_ocultas", []))


def usuario_pode_acessar_recurso(user: "User", recurso: str) -> bool:
    liberados = getattr(user, "recursos_liberados", None)
    if isinstance(liberados, list):
        return recurso in normalizar_recursos_liberados(liberados)
    return recurso not in normalizar_recursos_ocultos(getattr(user, "recursos_ocultos", []))


def ensure_user_schema(engine: Engine) -> None:
    """Migra colunas pequenas do auth sem depender de Alembic nesta fase."""
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("users")}
    except Exception as exc:  # noqa: BLE001
        log.warning("Nao foi possivel inspecionar schema de users: %s", exc)
        return
    dialect = engine.dialect.name
    missing: list[tuple[str, str]] = []
    if "paginas_ocultas" not in cols:
        missing.append(("paginas_ocultas", "Coluna users.paginas_ocultas criada."))
    if "recursos_ocultos" not in cols:
        missing.append(("recursos_ocultos", "Coluna users.recursos_ocultos criada."))
    allow_missing: list[tuple[str, str]] = []
    if "paginas_liberadas" not in cols:
        allow_missing.append(("paginas_liberadas", "Coluna users.paginas_liberadas criada."))
    if "recursos_liberados" not in cols:
        allow_missing.append(("recursos_liberados", "Coluna users.recursos_liberados criada."))

    if not missing and not allow_missing:
        return

    default = "'[]'::json" if dialect == "postgresql" else "'[]'"
    with engine.begin() as conn:
        for col, msg in missing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} JSON NOT NULL DEFAULT {default}"))
            log.info(msg)
        for col, msg in allow_missing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} JSON"))
            log.info(msg)


def backfill_user_access_allowlists(db: Session) -> None:
    """Inicializa permissao positiva a partir do modelo antigo de ocultos."""
    changed = False
    for user in db.execute(select(User)).scalars():
        if getattr(user, "paginas_liberadas", None) is None:
            user.paginas_liberadas = paginas_liberadas_por_ocultas(user.paginas_ocultas)
            changed = True
        if getattr(user, "recursos_liberados", None) is None:
            user.recursos_liberados = recursos_liberados_por_ocultos(user.recursos_ocultos)
            changed = True
    if changed:
        db.commit()
        log.info("Permissoes positivas de usuarios inicializadas.")


def renomear_victor_carbonero(db: Session) -> None:
    """Ajuste solicitado: Victor Costa deve aparecer como Carbonero."""
    changed = False
    for user in db.execute(
        select(User).where(
            (User.nome == "Victor Costa") |
            (func.lower(User.email) == "victor@nevoni.com.br")
        )
    ).scalars():
        user.nome = "Carbonero"
        changed = True
    if changed:
        db.commit()
        log.info("Usuario Victor Costa renomeado para Carbonero.")


def nome_publico_usuario(u: "User") -> str:
    email = (getattr(u, "email", "") or "").strip().lower()
    nome = (getattr(u, "nome", "") or "").strip()
    if email == "victor@nevoni.com.br" or nome == "Victor Costa":
        return "Carbonero"
    return nome


# ---------------------------------------------------------------------------
# Modelo ORM
# ---------------------------------------------------------------------------

class User(Base):
    """
    Usuário do Nevoni 360. Segue estritamente o contrato global (users):
    email único, senha_hash (bcrypt_sha256) e três flags de capabilities
    (is_admin, pode_editar_metas, pode_usar_oraculo).

    `precisa_trocar_senha` começa True (primeiro login ou reset pelo ADM)
    para forçar o usuário a definir uma senha própria antes de continuar.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nome = Column(String(255), nullable=False)
    senha_hash = Column(String(255), nullable=False)

    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    pode_editar_metas = Column(Boolean, nullable=False, default=False, server_default="false")
    pode_usar_oraculo = Column(Boolean, nullable=False, default=False, server_default="false")
    paginas_ocultas = Column(JSON, nullable=False, default=list, server_default="[]")
    recursos_ocultos = Column(JSON, nullable=False, default=list, server_default="[]")
    paginas_liberadas = Column(JSON, nullable=True, default=None)
    recursos_liberados = Column(JSON, nullable=True, default=None)

    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    precisa_trocar_senha = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    # Aceita string simples para evitar dependência do email-validator; a
    # normalização (strip+lower) e o unique constraint no banco cuidam de
    # duplicidades. Validação estrita de formato é responsabilidade do front.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class TrocarSenhaIn(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=255)
    nova_senha: str = Field(min_length=6, max_length=255)


class UserOut(BaseModel):
    """Payload público do usuário — nunca inclui hash da senha."""
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
    precisa_trocar_senha: bool


def _to_user_out(u: User) -> UserOut:
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
        precisa_trocar_senha=bool(u.precisa_trocar_senha),
    )


# ---------------------------------------------------------------------------
# Dependências
# ---------------------------------------------------------------------------

def get_current_user(
    db: Session = Depends(get_db),
    nevoni_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> User:
    """
    Recupera o usuário da requisição a partir do cookie de sessão.

    Retorna 401 quando: cookie ausente, JWT inválido/expirado, usuário
    inexistente ou inativo. Mensagem genérica para não vazar detalhe.
    """
    unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada.",
    )
    if not nevoni_session:
        raise unauth
    payload = decode_token(nevoni_session)
    if not payload:
        raise unauth
    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        user_id = None
    if user_id is None:
        raise unauth

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauth
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Restringe a ação a administradores. 403 quando o usuário não é admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ação restrita a administradores.",
        )
    return user


def require_editar_metas(user: User = Depends(get_current_user)) -> User:
    """Autoriza edição de metas para admin ou usuário com a capability."""
    if not (user.is_admin or user.pode_editar_metas):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para editar metas.",
        )
    return user


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    """
    Valida credenciais, seta o cookie httpOnly e devolve o payload do usuário.

    401 genérico cobre email inexistente, senha errada ou usuário inativo —
    evita revelar qual dos três falhou.
    """
    unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email ou senha inválidos.",
    )
    email_norm = body.email.strip().lower()
    user = db.execute(
        select(User).where(func.lower(User.email) == email_norm)
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauth
    if not verify_password(body.password, user.senha_hash):
        raise unauth

    user.last_login_at = datetime.now(tz=timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    set_session_cookie(response, token)
    return {"user": _to_user_out(user).model_dump()}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """Encerra a sessão apagando o cookie httpOnly."""
    clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Retorna o usuário logado (usado pelo React para hidratar a sessão)."""
    return {"user": _to_user_out(user).model_dump()}


@router.post("/trocar-senha")
def trocar_senha(
    body: TrocarSenhaIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Troca a senha do usuário logado. Exige a senha atual correta.

    Após a troca, o flag `precisa_trocar_senha` é baixado — o usuário passa a
    poder navegar normalmente sem o modal de troca obrigatória.
    """
    if not verify_password(body.senha_atual, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )
    user.senha_hash = hash_password(body.nova_senha)
    user.precisa_trocar_senha = False
    db.add(user)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bootstrap do admin master
# ---------------------------------------------------------------------------

def bootstrap_admin(db: Session) -> None:
    """
    Cria o ADM master a partir das envs quando a tabela `users` está vazia.

    Lê ADMIN_EMAIL (default: admnevoni@nevoni.com.br) e ADMIN_PASSWORD (obrigatório).
    Se a env de senha não vier setada, apenas emite warning — a API sobe, mas o
    login fica indisponível até um admin ser criado por outra via. Todas as
    capabilities ficam em True e `precisa_trocar_senha=True` para forçar a
    troca no primeiro acesso.
    """
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    if total and total > 0:
        return

    admin_email = os.getenv("ADMIN_EMAIL", "admnevoni@nevoni.com.br").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if not admin_password:
        log.warning(
            "Bootstrap do admin ignorado: ADMIN_PASSWORD não definido. "
            "A API sobe, mas o login ficará indisponível até criar um admin."
        )
        return

    admin = User(
        email=admin_email,
        nome="Administrador Nevoni",
        senha_hash=hash_password(admin_password),
        is_admin=True,
        pode_editar_metas=True,
        pode_usar_oraculo=True,
        paginas_liberadas=sorted(PAGINAS_CONTROLADAS),
        recursos_liberados=sorted(RECURSOS_CONTROLADOS),
        is_active=True,
        precisa_trocar_senha=True,
    )
    db.add(admin)
    db.commit()
    log.info("Admin master criado (email=%s).", admin_email)
