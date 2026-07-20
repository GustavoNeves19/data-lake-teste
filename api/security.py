"""
Primitivas de segurança do backend Nevoni 360.

Concentra num único ponto:
- Hash e verificação de senha (bcrypt_sha256, evita o limite de 72 bytes do bcrypt puro).
- Emissão e decodificação de JWT (HS256, assinado com JWT_SECRET).
- Set/clear do cookie httpOnly de sessão (nevoni_session).

Consumido por api/auth.py (endpoints de autenticação) e pelo middleware que
protege as rotas /api/*.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Response
from jose import JWTError, jwt
from passlib.context import CryptContext


log = logging.getLogger("nevoni.security")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JWT_SECRET: str = os.getenv("JWT_SECRET", "")
JWT_ALG: str = "HS256"
COOKIE_NAME: str = "nevoni_session"
TOKEN_DAYS: int = 7


def _is_production() -> bool:
    """Cookie Secure só quando o backend está em produção (HTTPS)."""
    return os.getenv("NEVONI_ENV", "").lower() == "production"


# ---------------------------------------------------------------------------
# Hash de senha (bcrypt_sha256)
# ---------------------------------------------------------------------------

# bcrypt_sha256 faz um SHA-256 antes do bcrypt: contorna o limite de 72 bytes
# do bcrypt puro e mantém o mesmo custo/segurança. Compatível com passlib.
_pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(pw: str) -> str:
    """Gera o hash da senha em texto plano (bcrypt_sha256)."""
    return _pwd_context.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    """Compara senha em texto plano com o hash guardado. Nunca lança."""
    if not pw or not hashed:
        return False
    try:
        return _pwd_context.verify(pw, hashed)
    except Exception:  # noqa: BLE001
        # Hash malformado ou incompatível: trata como falha de autenticação.
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_token(user_id: int) -> str:
    """
    Assina um JWT curto contendo o id do usuário e a expiração.

    Payload: {"sub": "<user_id>", "iat": <epoch>, "exp": <epoch+TOKEN_DAYS>}.
    Sem JWT_SECRET não deve emitir token — protege contra deploy mal
    configurado (segredo padrão em branco quebraria a assinatura silenciosa).
    """
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET não configurado no ambiente.")

    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    """
    Decodifica e valida o JWT. Retorna o payload ou None se inválido/expirado.

    Retorno silencioso (None) para que os callers tratem como 401 sem vazar
    detalhe do erro para o cliente.
    """
    if not token or not JWT_SECRET:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Cookie de sessão
# ---------------------------------------------------------------------------

def set_session_cookie(response: Response, token: str) -> None:
    """
    Grava o cookie httpOnly da sessão. Secure só em produção (HTTPS).

    SameSite=Lax evita CSRF em requisições cross-site comuns; Path=/ garante
    o envio em toda a API. max_age espelha a expiração do JWT.
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=TOKEN_DAYS * 24 * 3600,
        httponly=True,
        secure=_is_production(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove o cookie de sessão (logout)."""
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_is_production(),
        samesite="lax",
    )
