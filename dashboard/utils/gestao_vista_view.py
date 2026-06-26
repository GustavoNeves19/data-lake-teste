# -*- coding: utf-8 -*-
"""Painel de Gestão à Vista — função render() reutilizável.

Restruturação reunião 16/06/2026 (Alves):
  • Removidos: faturamento realizado, projeção de fechamento, venda necessária/dia.
  • Ranking vira DOIS: mensal (% meta) + diário (% do ritmo, com carry-over).
  • Karina e Eduardo fora do ranking (Eduardo não tem meta).
  • 2 pipelines abertas (Hospitalar + Farmácia) + 2 engenharia reversa.
  • Atividades por TIPO (ranqueadas) + NOVO bloco atividades por VENDEDOR.
  • Filtro de período (intervalo de datas) para as atividades.
Meta diária = meta mensal ÷ dias úteis. Canceladas: COM (até o Fred confirmar, qui).
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from dashboard.utils.bq_client import query, fmt_brl, PROJECT_PROD, data_ultima_carga
from dashboard.utils import gestao_vista as gv

PROJ   = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
CRM    = f"{PROJ}.crm_raw"

VIEWS = {
    "Geral":      ("GERAL",      "o.salesperson_group_code IN ('FA','FR','PC')"),
    "Hospitalar": ("HOSPITALAR", "o.salesperson_group_code = 'FA'"),
    "Farmácia":   ("FARMACIA",   "o.salesperson_group_code = 'FR'"),
}
NAT_JOIN = f"JOIN `{ORDERS}.dim_operation_nature` n ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'"

# Pipelines do CRM por canal (2 distintas — Alves: ambas no painel geral)
PIPE_HOSP  = ["funil_vendas_distribuidores", "recorrencia_distribuidores"]
PIPE_FARMA = ["funil_vendas_farmacia", "recorrencia_farmacia"]

# Estágios que entram no funil (reunião 16/06, Vinícius). Remove "A trabalhar"
# (clientes não trabalhados, sem deal real) e estágios de pré-funil (Contato etc.).
STAGES_HOSP  = ["Orçamento", "Negociação", "Fechamento"]
STAGES_FARMA = ["Negociação", "Fechamento"]

# Fora do ranking (decisão 16/06): Eduardo (licitação, sem meta) + Karina (distribuidor).
# UPPER() porque LIKE no BQ é case-sensitive e salesperson_name vem em MAIÚSCULAS.
EXCLUI = ("AND UPPER(o.salesperson_name) NOT LIKE 'EDUARDO%' "
          "AND UPPER(o.salesperson_name) NOT LIKE 'KARINA%'")

MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

TIPO_ATIV = {
    "call": "Chamada", "meeting": "Reunião", "task": "Tarefa", "deadline": "Prazo",
    "email": "E-mail", "lunch": "Almoço", "tentativa_de_contato": "Tentativa de contato",
    "contato": "Contato", "elaboracao_de_orcamento": "Elaboração de orçamento",
    "envio_de_orcamento": "Envio de orçamento", "aceite_do_cliente": "Aceite do cliente",
    "quebra_de_objecoes": "Quebra de objeções", "mensagem_de_despedida": "Mensagem de despedida",
    "checklist_de_qualificacao": "Checklist qualificação", "ligacao_atendida": "Ligação atendida",
    "nao_atendida": "Não atendida", "whatsapp_chat": "Whatsapp", "anexar_documentos": "Anexar docs",
    "validar_documentacao": "Validar documentação",
}
_pal = ["#185FA5", "#1D9E75", "#BA7517", "#7F77DD", "#D85A30", "#0F6E56", "#A33D8A", "#3C7A1E"]


def brl_k(v: float) -> str:
    v = float(v or 0)
    if abs(v) >= 1_000_000:
        return f"R$ {v/1_000_000:.1f}M".replace(".", ",")
    if abs(v) >= 1_000:
        return f"R$ {v/1_000:.0f}k"
    return f"R$ {v:.0f}"


def gauge_svg(pct: float) -> str:
    L = 201.06
    frac = max(0.0, min(pct, 1.0))
    cor = "#1D9E75" if pct >= 0.85 else ("#D97706" if pct >= 0.5 else "#DC2626")
    return (
        f'<svg viewBox="0 0 164 96" width="140">'
        f'<path d="M18,84 A64,64 0 0 1 146,84" fill="none" stroke="#EEF0FF" stroke-width="14" stroke-linecap="round"/>'
        f'<path d="M18,84 A64,64 0 0 1 146,84" fill="none" stroke="{cor}" stroke-width="14" '
        f'stroke-linecap="round" stroke-dasharray="{frac*L:.1f} {L}"/>'
        f'<text x="82" y="78" text-anchor="middle" font-size="30" font-weight="600" fill="#15151F">{pct*100:.0f}%</text>'
        f'</svg>'
    )


def card(badge_n, badge_bg, badge_fg, title, inner, wide=False) -> str:
    cls = "gv-card gv-wide" if wide else "gv-card"
    return (
        f'<div class="{cls}"><div class="gv-head">'
        f'<span class="gv-badge" style="background:{badge_bg};color:{badge_fg};">{badge_n}</span>'
        f'<span class="gv-title">{title}</span></div>{inner}</div>'
    )


def _rank_rows(itens) -> str:
    """itens = [(nome, pct|None)] já ordenado. Renderiza barras de % (sem valor)."""
    out = ""
    for nome, pct in itens:
        if pct is None:
            out += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                    f'<span style="color:#15151F;">{nome}</span><span style="color:#8A8A99;">—</span></div>'
                    f'<div class="gv-bar-track"><div class="gv-bar-fill" style="width:0%;background:#C9C9D4;"></div></div></div>')
            continue
        cor = "#1D9E75" if pct >= 0.9 else ("#BA7517" if pct >= 0.5 else "#E24B4A")
        out += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                f'<span style="color:#15151F;">{nome}</span>'
                f'<span style="color:#8A8A99;">{pct*100:.0f}%</span></div>'
                f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                f'style="width:{min(pct,1)*100:.0f}%;background:{cor};"></div></div></div>')
    return out or '<div class="gv-sub" style="padding:8px 0;">Sem vendedor com meta nesta visão.</div>'


def _pipeline_stats(tables: list, allowed: list):
    """Estatísticas de um conjunto de pipelines do CRM (funil aberto + win rate).
    `allowed` = estágios do funil a exibir, na sequência orçamento→negociação→fechamento.
    "A trabalhar" e pré-funil (Contato etc.) ficam fora do funil E do total em aberto."""
    union = "\n UNION ALL ".join(
        f"SELECT deal_id, value, status, stage_id FROM `{CRM}.{t}` WHERE is_deleted IS NOT TRUE"
        for t in tables
    )
    out = {"df": None, "pipe_open": 0.0, "win_rate": 0.0, "ticket_won": 0.0, "won": 0, "lost": 0}
    allowed_sql = ", ".join(f"'{s}'" for s in allowed)
    try:
        raw = query(f"""
            WITH d AS ({union})
            SELECT s.stage_name nome, SUM(CAST(d.value AS FLOAT64)) val, COUNT(*) n
            FROM d JOIN `{CRM}.dim_crm_stage` s ON s.stage_id = d.stage_id
            WHERE d.status = 'open' AND s.stage_name IN ({allowed_sql})
            GROUP BY 1
        """)
        existing = {r["nome"]: (float(r["val"] or 0), int(r["n"] or 0)) for _, r in raw.iterrows()}
        # mostra TODOS os estágios do funil, na ordem, MESMO com 0 (Vinícius: estrutura
        # completa — ex.: Farmácia tem que ter Negociação E Fechamento, mesmo zerado).
        df = pd.DataFrame([{"nome": s, "val": existing.get(s, (0.0, 0))[0],
                            "n": existing.get(s, (0.0, 0))[1]} for s in allowed])
        st_df = query(f"""
            WITH d AS ({union})
            SELECT COUNTIF(status='won') won, COUNTIF(status='lost') lost,
                   SUM(IF(status='won', CAST(value AS FLOAT64), 0)) val_won
            FROM d
        """)
        r0 = st_df.iloc[0]
        won, lost = int(r0["won"] or 0), int(r0["lost"] or 0)
        out.update(df=df, pipe_open=float(df["val"].sum()), won=won, lost=lost,
                   win_rate=(won / (won + lost) if (won + lost) else 0.0),
                   ticket_won=(float(r0["val_won"] or 0) / won if won else 0.0))
    except Exception:
        pass
    return out


def _pipe_card(badge_n, titulo, stats: dict) -> str:
    df = stats["df"]
    if df is None or df.empty:
        inner = '<div class="gv-sub" style="padding:8px 0;">Sem pipeline próprio no CRM.</div>'
        nota = "Sem deals em aberto nesta pipeline"
    else:
        vmax = float(df["val"].max()) or 1.0
        inner = (f'<div class="gv-hero" style="font-size:22px;margin-bottom:10px;">{brl_k(stats["pipe_open"])}'
                 f'<span style="font-size:13px;color:#8A8A99;font-weight:400;"> em aberto</span></div>')
        for _, rw in df.iterrows():
            w = max(rw["val"] / vmax * 100, 3)
            inner += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                      f'<span style="color:#15151F;">{rw["nome"]}</span>'
                      f'<span style="color:#8A8A99;">{brl_k(rw["val"])}</span></div>'
                      f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                      f'style="width:{w:.0f}%;background:#378ADD;"></div></div></div>')
        nota = "Pipedrive ao vivo · top estágios por valor"
    return card(badge_n, "#E6F1FB", "#0C447C", titulo, inner + f'<div class="gv-note">{nota}</div>')


def _eng_reversa_card(badge_n, titulo, users: list) -> str:
    """Funil reverso do Alves, POR USUÁRIO (decisão 23/06): o total do time no topo
    (hero) e, abaixo, cada vendedor com sua meta e o esforco (contatos/dia) pra bater."""
    if not users:
        return card(badge_n, "#F1EFE8", "#444441", titulo,
            '<div class="gv-sub" style="padding:8px 0;">Sem vendedor com meta nesta visao.</div>'
            '<div class="gv-note">Metas do Pipedrive + taxas da planilha do Alves</div>', wide=True)
    meta_tot = sum(u["meta"] for u in users)
    cd_tot   = sum(u["contatos_dia"] for u in users)
    vmax = max((u["contatos_dia"] for u in users), default=1) or 1
    inner = (
        f'<div class="gv-hero gv-effort">{cd_tot:.0f}'
        f'<span style="font-size:13px;color:#8A8A99;font-weight:400;"> contatos/dia (time)</span></div>'
        f'<div class="gv-sub">esforço do time pra bater {fmt_brl(meta_tot)}</div>'
        '<div style="margin-top:12px;">')
    for u in users:
        flag = (' <span style="font-size:11px;color:#854F0B;background:#FAEEDA;'
                'padding:1px 6px;border-radius:6px;">aprox.</span>') if u["aprox"] else ''
        w = max(u["contatos_dia"] / vmax * 100, 3)
        inner += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                  f'<span style="color:#15151F;">{u["nome"]}{flag}</span>'
                  f'<span style="color:#8A8A99;">{brl_k(u["meta"])} · {u["contatos_dia"]:.0f}/dia</span></div>'
                  f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                  f'style="width:{w:.0f}%;background:#7E746B;"></div></div></div>')
    inner += '</div>'
    return card(badge_n, "#F1EFE8", "#444441", titulo,
                inner + '<div class="gv-note">Por vendedor: meta (Pipedrive) ÷ ticket ÷ taxas de conversão (planilha Alves)</div>',
                wide=True)


def render(key_prefix: str = "gv"):
    """Renderiza o painel de Gestão à Vista no container atual."""
    st.markdown(f'<div class="gv-band"><div><p class="t">Painel de Gestão à Vista</p>'
                f'<p class="s">Meta · ritmo · pipeline da equipe de vendas · '
                f'dados de {data_ultima_carga()} BRT</p></div>'
                f'<p class="s">Geral inclui Marketplace · visões por canal sem Marketplace · SAC entra no Hospitalar em julho</p></div>',
                unsafe_allow_html=True)

    # ── controles: visão · mês ───────────────────────────────────────────────
    # Filtro de período (intervalo) e seletor de vendedor removidos: o painel é
    # panorâmico (a equipe de relance), não análise individual — o seletor só
    # cortava 1 dos 9 blocos (Atividades por tipo) e confundia. Tudo no mês.
    try:
        dfm = query(f"""
            SELECT DISTINCT DATE_TRUNC(o.invoice_date, MONTH) m
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE o.invoice_date >= '2026-01-01' AND o.invoice_date IS NOT NULL
            ORDER BY m DESC
        """)
        meses = [d.date() if hasattr(d, "date") else d for d in dfm["m"].tolist()]
    except Exception as e:
        st.error(f"Erro ao listar meses: {e}")
        return

    c1, c2 = st.columns([4, 1])
    with c1:
        view_label = st.radio("Visão", list(VIEWS), horizontal=True,
                              label_visibility="collapsed", key=f"{key_prefix}_view")
    view_key, group_filter = VIEWS[view_label]
    with c2:
        mes_sel = st.selectbox("Mês", meses, format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}",
                               label_visibility="collapsed", key=f"{key_prefix}_mes")
    vend_at = "Todos"   # painel panorâmico: Atividades por tipo mostra a equipe toda

    mes_ini = mes_sel
    mes_fim = date(mes_sel.year + (mes_sel.month == 12), (mes_sel.month % 12) + 1, 1)
    hoje = date.today()
    eh_mes_corrente = (mes_sel.year == hoje.year and mes_sel.month == hoje.month)
    ref = hoje if eh_mes_corrente else date.fromordinal(mes_fim.toordinal() - 1)

    meta = gv.META_EQUIPE[view_key]
    mes_key = f"{mes_sel.year:04d}-{mes_sel.month:02d}"
    du_total = gv.dias_uteis_mes(ref)
    du_corr  = gv.dia_util_corrente(ref)

    with st.spinner("Consultando BigQuery..."):
        # faturamento do mês (visão) — COM canceladas (até o Fred confirmar)
        df_fat = query(f"""
            SELECT SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE {group_filter}
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
        """)
        faturado_mes = float(df_fat["v"].iloc[0] or 0)

        # faturamento por canal (FA/FR/PC + Marketplace) — realizado por canal no bloco 1.
        # Marketplace (MKT) = EC (e-commerce) + vendas sem grupo (Mercado Livre/Shopee);
        # entra só no Geral (Alves 23/06). LI/licitação fica fora pelo WHERE.
        df_grp = query(f"""
            SELECT
              CASE WHEN o.salesperson_group_code IN ('FA','FR','PC')
                   THEN o.salesperson_group_code ELSE 'MKT' END g,
              SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE (o.salesperson_group_code IN ('FA','FR','PC','EC') OR o.salesperson_group_code IS NULL)
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
            GROUP BY 1
        """)
        fat_grp = {r["g"]: float(r["v"] or 0) for _, r in df_grp.iterrows()}
        # Geral soma o Marketplace no realizado (Alves 23/06); visões por canal não.
        if view_key == "GERAL":
            faturado_mes += fat_grp.get("MKT", 0.0)

        # realizado por vendedor (visão, sem Eduardo/Karina) — base dos 2 rankings
        df_rk = query(f"""
            SELECT INITCAP(LOWER(TRIM(o.salesperson_name))) nome,
                   UPPER(TRIM(o.salesperson_name)) nome_norm,
                   SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE {group_filter}
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
              AND o.salesperson_name IS NOT NULL AND TRIM(o.salesperson_name) <> ''
              {EXCLUI}
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
        """)
        df_rk["v"] = df_rk["v"].astype(float)

        # agrupamento vendedor->família vindo do ERP (YGRUVEN), pra a engenharia reversa
        # por usuário sem hardcode (regra Diego 23/06). Prefere FA quando há 2 cadastros.
        try:
            df_grupo = query(f"""
                SELECT salesperson_name nome, salesperson_group_code g
                FROM `{ORDERS}.dim_salesperson`
                WHERE is_active AND salesperson_group_code IN ('FA','FR','PC')
                QUALIFY ROW_NUMBER() OVER (PARTITION BY salesperson_name
                    ORDER BY CASE salesperson_group_code
                        WHEN 'FA' THEN 1 WHEN 'FR' THEN 2 ELSE 3 END) = 1
            """)
            grupo_de = {r["nome"]: r["g"] for _, r in df_grupo.iterrows()}
        except Exception:
            grupo_de = {}

        stats_hosp  = _pipeline_stats(PIPE_HOSP, STAGES_HOSP)
        stats_farma = _pipeline_stats(PIPE_FARMA, STAGES_FARMA)

        # atividades por TIPO (feitas no mês + atrasadas) — filtra por vendedor (Alves)
        _vesc = vend_at.replace("'", "''")
        vend_filtro = "" if vend_at == "Todos" else f"AND u.name = '{_vesc}'"
        try:
            df_at = query(f"""
                SELECT a.type tipo,
                       COUNTIF(a.done AND a.due_date >= '{mes_ini}' AND a.due_date < '{mes_fim}') concl,
                       COUNTIF(NOT a.done AND a.due_date < CURRENT_DATE()) atras
                FROM `{CRM}.activities` a
                LEFT JOIN `{CRM}.dim_crm_user` u ON u.user_id = a.user_id
                WHERE a.user_id IS NOT NULL {vend_filtro}
                GROUP BY 1 HAVING concl > 0 OR atras > 0
                ORDER BY concl DESC LIMIT 8
            """)
        except Exception:
            df_at = None

        # atividades por VENDEDOR (novo) — sem Eduardo/Karina
        try:
            df_av = query(f"""
                SELECT u.name vend,
                       COUNTIF(a.done AND a.due_date >= '{mes_ini}' AND a.due_date < '{mes_fim}') concl,
                       COUNTIF(NOT a.done AND a.due_date < CURRENT_DATE()) atras
                FROM `{CRM}.activities` a
                JOIN `{CRM}.dim_crm_user` u ON u.user_id = a.user_id
                WHERE UPPER(u.name) NOT LIKE 'EDUARDO%' AND UPPER(u.name) NOT LIKE 'KARINA%'
                  AND UPPER(u.name) NOT LIKE 'VICTOR%' AND UPPER(u.name) NOT LIKE 'CLARICE%'
                GROUP BY 1 HAVING concl > 0 OR atras > 0
                ORDER BY concl DESC LIMIT 8
            """)
        except Exception:
            df_av = None

    # ── KPIs derivados ──────────────────────────────────────────────────────
    pct_meta = faturado_mes / meta if meta else 0
    falta    = max(meta - faturado_mes, 0.0)

    cards = []

    # 1 — % da meta da equipe (gauge) + realizado por canal (Vinícius 16/06)
    # Marketplace só aparece no Geral (Alves 23/06: nas visões por canal ele fica fora).
    _mkt_chip = (f'<div><div class="lbl">Marketplace</div>'
                 f'<div class="val">{brl_k(fat_grp.get("MKT", 0))}</div></div>'
                 if view_key == "GERAL" else "")
    chan = (
        f'<div class="gv-chan">'
        f'<div><div class="lbl">Hospitalar</div><div class="val">{brl_k(fat_grp.get("FA", 0))}</div></div>'
        f'<div><div class="lbl">Farmácia</div><div class="val">{brl_k(fat_grp.get("FR", 0))}</div></div>'
        f'<div><div class="lbl">SAC</div><div class="val">{brl_k(fat_grp.get("PC", 0))}</div></div>'
        f'{_mkt_chip}'
        f'</div>')
    cards.append(card("1", "#E1F5EE", "#0F6E56", "% da meta da equipe",
        f'<div style="display:flex;align-items:center;gap:14px;">{gauge_svg(pct_meta)}'
        f'<div style="font-size:12px;color:#8A8A99;line-height:1.7;">Meta<br>'
        f'<span style="color:#15151F;font-weight:600;">{fmt_brl(meta)}</span><br>Realizado<br>'
        f'<span style="color:#15151F;font-weight:600;">{fmt_brl(faturado_mes)}</span></div></div>'
        f'<div class="gv-sub">Falta: <span style="color:#DC2626;font-weight:600;">{fmt_brl(falta)}</span>'
        f' ({(falta/meta if meta else 0)*100:.0f}%)</div>'
        f'<div class="gv-sub" style="margin-top:9px;color:#15151F;font-weight:600;">Realizado por canal</div>{chan}',
        wide=True))

    # 2 — Ranking MENSAL (% da meta individual) — só vendedores com meta
    rk_m = []
    for _, r in df_rk.iterrows():
        meta_ind = gv.METAS_VENDEDOR.get(r["nome_norm"], {}).get(mes_key)
        if not meta_ind:
            continue
        rk_m.append((r["nome"], r["v"] / meta_ind))
    rk_m.sort(key=lambda x: x[1], reverse=True)
    cards.append(card("2", "#E1F5EE", "#0F6E56", "Ranking mensal", _rank_rows(rk_m) +
        '<div class="gv-note">% da meta mensal individual (Pipedrive)</div>'))

    # 3 — Ranking DIÁRIO (% do ritmo: realizado ÷ meta pro-rata até hoje, com carry-over)
    rk_d = []
    for _, r in df_rk.iterrows():
        meta_ind = gv.METAS_VENDEDOR.get(r["nome_norm"], {}).get(mes_key)
        if not meta_ind:
            continue
        alvo_hoje = meta_ind / du_total * du_corr
        rk_d.append((r["nome"], (r["v"] / alvo_hoje) if alvo_hoje else None))
    rk_d.sort(key=lambda x: (x[1] if x[1] is not None else -1), reverse=True)
    cards.append(card("3", "#EEEDFE", "#3C3489", "Ranking diário", _rank_rows(rk_d) +
        f'<div class="gv-note">% do ritmo até hoje · meta diária = mensal ÷ {du_total} dias úteis '
        f'(dia útil {du_corr}/{du_total}) · remanescente rola pro dia seguinte</div>'))

    # 4 — Venda necessária por dia, por vendedor (Alves 23/06; dias úteis seg-sex menos
    # feriado, confirmado 25/06). = (meta − realizado) ÷ dias úteis restantes do mês.
    du_rest = gv.dias_uteis_restantes(ref)
    vnd = []
    for _, r in df_rk.iterrows():
        meta_ind = gv.METAS_VENDEDOR.get(r["nome_norm"], {}).get(mes_key)
        if not meta_ind:
            continue
        vnd.append((r["nome"], gv.venda_necessaria_dia(meta_ind, r["v"], ref), r["v"] >= meta_ind))
    vnd.sort(key=lambda x: x[1], reverse=True)
    if vnd:
        vmax_d = max((v for _, v, _ in vnd), default=1.0) or 1.0
        rows_vnd = ""
        for nome, vdia, batida in vnd:
            if batida:
                rows_vnd += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                             f'<span style="color:#15151F;">{nome}</span>'
                             f'<span style="color:#1D9E75;font-weight:600;">✓ meta batida</span></div>'
                             f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                             f'style="width:100%;background:#1D9E75;"></div></div></div>')
            else:
                w = max(vdia / vmax_d * 100, 4)
                rows_vnd += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                             f'<span style="color:#15151F;">{nome}</span>'
                             f'<span style="color:#3C3489;font-weight:600;">{fmt_brl(vdia)}/dia</span></div>'
                             f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                             f'style="width:{w:.0f}%;background:#6D5FD6;"></div></div></div>')
    else:
        rows_vnd = '<div class="gv-sub" style="padding:8px 0;">Sem vendedor com meta nesta visão.</div>'
    cards.append(card("4", "#EEEDFE", "#3C3489", "Venda necessária por dia", rows_vnd +
        f'<div class="gv-note">(meta − realizado) ÷ {du_rest} dias úteis restantes (contando hoje) · '
        f'seg-sex sem feriado · ordenado pelo que falta mais por dia</div>'))

    # 5 e 6 — Pipelines abertas (Hospitalar + Farmácia)
    cards.append(_pipe_card("5", "Pipeline aberto — Hospitalar", stats_hosp))
    cards.append(_pipe_card("6", "Pipeline aberto — Farmácia", stats_farma))

    # 6 e 7 — Engenharia reversa POR USUÁRIO (Alves 23/06): meta do Pipe + taxas da
    # planilha do Alves + agrupamento do ERP (sem hardcode, regra Diego). Kauan Ramos
    # aproximado pela média do Hospitalar até o Alves cadastrar a taxa dele.
    def _eng_familia(grupo_cod):
        users = []
        for nome_norm, metas in gv.METAS_VENDEDOR.items():
            if grupo_de.get(nome_norm) != grupo_cod:
                continue
            meta_ind = metas.get(mes_key)
            if not meta_ind:
                continue
            taxas = gv.TAXAS_CONVERSAO.get(nome_norm)
            aprox = taxas is None
            if aprox:
                taxas = gv.taxas_aproximadas_hospitalar()
            f = gv.eng_reversa_funil(meta_ind, taxas, du_total)
            users.append({"nome": nome_norm.title(), "aprox": aprox, **f})
        users.sort(key=lambda u: u["meta"], reverse=True)
        return users
    cards.append(_eng_reversa_card("7", "Engenharia reversa — Hospitalar", _eng_familia("FA")))
    cards.append(_eng_reversa_card("8", "Engenharia reversa — Farmácia", _eng_familia("FR")))

    # 9 — Atividades por TIPO (ranqueadas)
    if df_at is not None and not df_at.empty:
        df_at["concl"] = df_at["concl"].astype(int)
        df_at["atras"] = df_at["atras"].astype(int)
        tot_c, tot_a = int(df_at["concl"].sum()), int(df_at["atras"].sum())
        vmax = max(int(df_at["concl"].max()), 1)
        rows = (f'<div class="gv-sub" style="margin-bottom:8px;">'
                f'<span style="color:#15151F;font-weight:600;">{tot_c} feitas</span> · '
                f'<span style="color:#DC2626;font-weight:600;">{tot_a} atrasadas</span> no mês</div>')
        for i, (_, r) in enumerate(df_at.iterrows()):
            nome = TIPO_ATIV.get(r["tipo"], r["tipo"])
            w = max(r["concl"] / vmax * 100, 3)
            late = f'<span class="gv-ativ-late">{r["atras"]} atras</span>' if r["atras"] > 0 else ''
            rows += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                     f'<span style="color:#15151F;">{nome}</span>'
                     f'<span style="display:flex;gap:7px;align-items:center;">'
                     f'<span class="gv-ativ-done">{r["concl"]}</span>{late}</span></div>'
                     f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                     f'style="width:{w:.0f}%;background:{_pal[i % len(_pal)]};"></div></div></div>')
        nota = (f"Ranqueado por feitas · {'toda a equipe' if vend_at == 'Todos' else vend_at}")
    else:
        rows = '<div class="gv-sub" style="padding:8px 0;">crm_raw.activities indisponível.</div>'
        nota = "Ingestão de atividades pendente"
    cards.append(card("9", "#FAEEDA", "#854F0B", "Atividades por tipo", rows + f'<div class="gv-note">{nota}</div>'))

    # 10 — Atividades por VENDEDOR (novo)
    if df_av is not None and not df_av.empty:
        df_av["concl"] = df_av["concl"].astype(int)
        df_av["atras"] = df_av["atras"].astype(int)
        vmax = max(int(df_av["concl"].max()), 1)
        rows = ""
        for i, (_, r) in enumerate(df_av.iterrows()):
            w = max(r["concl"] / vmax * 100, 3)
            late = f'<span class="gv-ativ-late">{r["atras"]} atras</span>' if r["atras"] > 0 else ''
            rows += (f'<div class="gv-rk-row"><div class="gv-rk-top">'
                     f'<span style="color:#15151F;">{r["vend"]}</span>'
                     f'<span style="display:flex;gap:7px;align-items:center;">'
                     f'<span class="gv-ativ-done">{r["concl"]}</span>{late}</span></div>'
                     f'<div class="gv-bar-track"><div class="gv-bar-fill" '
                     f'style="width:{w:.0f}%;background:{_pal[i % len(_pal)]};"></div></div></div>')
        nota = "Feitas no período · atrasadas (sem data no Pipedrive)"
    else:
        rows = '<div class="gv-sub" style="padding:8px 0;">Sem atividades por vendedor.</div>'
        nota = "Mapeamento user_id → vendedor (dim_crm_user)"
    cards.append(card("10", "#FAEEDA", "#854F0B", "Atividades por vendedor", rows + f'<div class="gv-note">{nota}</div>'))

    st.markdown(f'<div class="gv-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="gv-foot">★ Nosso foco, nosso resultado — disciplina todos os dias, '
                'resultados todos os meses.</div>', unsafe_allow_html=True)
    if gv.PROVISORIO:
        st.caption("⚠️ Metas provisórias (Pipedrive). Ranking diário com carry-over · meta diária = "
                   "mensal ÷ dias úteis. Karina e Eduardo fora do ranking. Faturamento COM canceladas "
                   "(até o Fred confirmar a flag, quinta).")
