"""
Metas editáveis por mês e por visão (GERAL/HOSPITALAR/FARMACIA).

Substitui a constante `META_EQUIPE` do gestao_vista.py por uma tabela
persistida em Postgres, editável por usuários com a permissão
`pode_editar_metas`. Quando não há linha cadastrada para (mes, view_key),
o consumo cai no fallback do gestao_vista.py (constante em memória), para
não quebrar telas em ambientes recém-provisionados.

Modelo:
  metas_equipe(mes DATE, view_key TEXT, meta NUMERIC(14,2),
               updated_by TEXT, updated_at TIMESTAMPTZ)
  PK composta (mes, view_key).

Rotas (todas montadas em /api/comercial):
  GET  /metas-equipe               — lista (autenticado)
  PUT  /metas-equipe               — upsert (requer pode_editar_metas)

Helper:
  meta_do_mes(db, mes, view_key)   — usada pelo gestao_vista.py para ler
                                     do Postgres antes do fallback.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, Numeric, String, Date, select
from sqlalchemy.orm import Session

from .db import Base, get_db
from .auth import get_current_user, require_editar_metas


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

# Visões permitidas para a meta (bate com VIEWS em gestao_vista.py).
VIEW_KEYS = ("GERAL", "HOSPITALAR", "FARMACIA")


class MetaEquipe(Base):
    """Meta mensal por visão (GERAL/HOSPITALAR/FARMACIA)."""

    __tablename__ = "metas_equipe"

    # Chave primária composta (mes, view_key).
    mes = Column(Date, primary_key=True, nullable=False)
    view_key = Column(String, primary_key=True, nullable=False)

    # Valor da meta em R$. NUMERIC(14,2) segura até ~R$ 999 bi com 2 casas.
    meta = Column(Numeric(14, 2), nullable=False)

    # Auditoria de quem editou por último.
    updated_by = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------

class MetaOut(BaseModel):
    """Linha de meta serializada para o frontend."""

    mes: str = Field(..., description="Data no formato YYYY-MM-DD (sempre dia 1).")
    view_key: str = Field(..., description="GERAL | HOSPITALAR | FARMACIA.")
    meta: float = Field(..., description="Valor da meta em reais.")
    updated_by: str
    updated_at: str = Field(..., description="ISO 8601 UTC.")


class MetaUpsertIn(BaseModel):
    """Payload do PUT /metas-equipe."""

    mes: str = Field(..., description="YYYY-MM-01 (aceita YYYY-MM-DD e normaliza).")
    view_key: Literal["GERAL", "HOSPITALAR", "FARMACIA"]
    meta: float = Field(..., ge=0, description="Meta em reais, não negativa.")

    @field_validator("mes")
    @classmethod
    def _parse_mes(cls, v: str) -> str:
        try:
            d = date.fromisoformat(v)
        except (TypeError, ValueError) as exc:
            raise ValueError("mes deve estar no formato YYYY-MM-DD.") from exc
        # Normaliza para o primeiro dia do mês (chave da tabela).
        return d.replace(day=1).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(row: MetaEquipe) -> dict:
    """Converte MetaEquipe em dict pronto para JSON (formatos estáveis)."""
    updated_at = row.updated_at
    if isinstance(updated_at, datetime):
        updated_at_iso = updated_at.isoformat()
    else:
        updated_at_iso = str(updated_at) if updated_at is not None else ""
    return {
        "mes": row.mes.isoformat() if isinstance(row.mes, date) else str(row.mes),
        "view_key": row.view_key,
        "meta": float(row.meta) if row.meta is not None else 0.0,
        "updated_by": row.updated_by or "",
        "updated_at": updated_at_iso,
    }


def meta_do_mes(db: Session, mes: date, view_key: str) -> float | None:
    """
    Retorna a meta persistida em Postgres para (mês, visão) ou None.

    Usada pelo gestao_vista.py como fonte primária; quando None, o chamador
    cai no fallback da constante META_EQUIPE em memória. Nunca levanta:
    se a tabela ainda não existe (banco sem `init_db`), devolve None.
    """
    if view_key not in VIEW_KEYS:
        return None
    mes_norm = mes.replace(day=1) if isinstance(mes, date) else mes
    try:
        row = db.execute(
            select(MetaEquipe.meta).where(
                MetaEquipe.mes == mes_norm,
                MetaEquipe.view_key == view_key,
            )
        ).scalar_one_or_none()
    except Exception:
        # Tabela ausente / banco caído: silencia para o fallback assumir.
        return None
    if row is None:
        return None
    return float(row)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/comercial", tags=["metas"])


@router.get("/metas-equipe", response_model=list[MetaOut])
def listar_metas_equipe(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[dict]:
    """
    Lista todas as metas cadastradas, ordenadas por mês (mais recente
    primeiro) e visão em ordem alfabética.
    """
    rows = db.execute(
        select(MetaEquipe).order_by(MetaEquipe.mes.desc(), MetaEquipe.view_key.asc())
    ).scalars().all()
    return [_serialize(r) for r in rows]


@router.put("/metas-equipe")
def upsert_meta_equipe(
    payload: MetaUpsertIn,
    db: Session = Depends(get_db),
    user=Depends(require_editar_metas),
) -> dict:
    """
    Cria ou atualiza a meta de (mes, view_key). Requer permissão
    `pode_editar_metas` (ou is_admin) — o guard `require_editar_metas`
    responde 403 caso contrário.
    """
    mes_norm = date.fromisoformat(payload.mes)
    email = getattr(user, "email", None) or ""
    if not email:
        # Segurança adicional: se o guard devolveu um user sem email,
        # tratamos como sessão inválida.
        raise HTTPException(status_code=401, detail="Sessão inválida.")

    row = db.execute(
        select(MetaEquipe).where(
            MetaEquipe.mes == mes_norm,
            MetaEquipe.view_key == payload.view_key,
        )
    ).scalar_one_or_none()

    now = datetime.utcnow()
    if row is None:
        row = MetaEquipe(
            mes=mes_norm,
            view_key=payload.view_key,
            meta=Decimal(str(payload.meta)),
            updated_by=email,
            updated_at=now,
        )
        db.add(row)
    else:
        row.meta = Decimal(str(payload.meta))
        row.updated_by = email
        row.updated_at = now

    db.commit()
    db.refresh(row)
    return {"ok": True, "meta": _serialize(row)}
