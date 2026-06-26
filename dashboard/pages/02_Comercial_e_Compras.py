"""
Comercial e Compras — Vendas · Compras · Orçamentos · CRM · Ranking Clientes
Gold primary → Bronze fallback automático
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Comercial e Compras | Nevoni 360°", page_icon="", layout="wide")

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dashboard.utils.components import inject_css, page_header, kpi_card, kpi_row, section_title, sidebar_brand
from dashboard.utils.bq_client import query, query_layer, fmt_brl, fmt_num, fmt_pct, PROJECT_PROD, data_ultima_carga
from dashboard.utils.gold_tables import Comercial as G
from dashboard.utils import gestao_vista as gv, metas_store, calendario_view

inject_css()
sidebar_brand()

PROJ   = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
QUOTES = f"{PROJ}.dm_quotes"

# Mapeia nomes curtos (silver legado) para nome completo + trata "Sem Vendedor"/NULL como "Cliente Novo".
# Aplicado em todas as queries de display do tab RFV. Não altera dados em BQ.
SP_DISPLAY = """CASE COALESCE(rfv_salesperson, 'Novos Clientes')
        WHEN 'Guilherme Aquino' THEN 'Carteira A'
        WHEN 'Guilherme'        THEN 'Carteira A'
        WHEN 'Kauã Rodrigues'   THEN 'Carteira B'
        WHEN 'Kaua'             THEN 'Carteira B'
        WHEN 'Kauã'             THEN 'Carteira B'
        WHEN 'Richard Lucas'    THEN 'Carteira C'
        WHEN 'Richard'          THEN 'Carteira C'
        WHEN 'Kauan Ramos'      THEN 'Carteira D'
        WHEN 'Ramos'            THEN 'Carteira D'
        WHEN 'Cauã Ribeiro'     THEN 'Farmácias'
        WHEN 'Ribeiro'          THEN 'Farmácias'
        WHEN 'Geovanna Gomes'   THEN 'SAC'
        WHEN 'Giovanna'         THEN 'SAC'
        WHEN 'Sem Vendedor'     THEN 'Novos Clientes'
        ELSE COALESCE(rfv_salesperson, 'Novos Clientes')
      END"""

# Predicado WHERE pra excluir resíduos da Geovanna em Hospitalar
# (4 clientes / R$ 7K — decisão Alves 25/05: Geovanna só SAC).
GIOVANNA_RESIDUO_FILTER = (
    "AND NOT (rfv_familia = 'HOSPITALAR' AND rfv_salesperson = 'Giovanna')"
)

page_header(
    title="Comercial e Compras",
    subtitle="Vendas · Compras · Orçamentos · CRM Funil · Ranking de Clientes",
    sources=[
        {"name": "gold_comercial",   "active": True},
        {"name": "ERP + Pipedrive",  "active": True},
    ],
)

st.caption(
    f"📅 Vendas/faturamento: foto de **{data_ultima_carga()} BRT** (última carga do ERP no BigQuery) · "
    f"Matriz RFV: snapshot do último mês fechado (janela de 12 meses)."
)

tab_venda, tab_diaria, tab_compra, tab_orc, tab_crm, tab_clientes, tab_rfv = st.tabs([
    "Vendas", "Gestão à Vista", "Compras", "Orçamentos", "Funil CRM", "Ranking Clientes", "Matriz RFV",
])

# ── Vendas ───────────────────────────────────────────────────
with tab_venda:
    # ═══ Dashboard Semanal de Liderança ═══════════════════════════════
    section_title("Dashboard Semanal de Liderança")

    SILVER_COM = f"{PROJ}.silver_comercial"
    st.caption("Meta semanal/mensal é definida manualmente pelo Vinícius (com carry-over entre semanas). Campo editável virá em versão futura — por enquanto, o comparativo é com Mês Anterior e Mesmo Mês do Ano Anterior.")

    # Marketplace codes (YCODVEN no ERP)
    MKT_CODES = ('AM','SH','SHOPEE','LI','OL','90','91','92','AME','000054')

    # Filtro de mês (default = Maio/2026)
    # Metodologia OFICIAL Alves (validada 03/06/2026): yTipOpe='S', yFinNat<>'N',
    # janela por yDatNot (invoice_date), valor = yValPro (product_amount).
    try:
        df_meses = query(f"""
            SELECT DISTINCT DATE_TRUNC(invoice_date, MONTH) AS mes
            FROM `{ORDERS}.fact_sales_order`
            WHERE invoice_date >= '2024-01-01' AND invoice_date IS NOT NULL
            ORDER BY 1 DESC LIMIT 30
        """)
        meses_list = pd.to_datetime(df_meses["mes"]).dt.date.tolist()
    except Exception:
        meses_list = []

    _MES_PT = {1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
               7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"}

    if meses_list:
        labels_mes = [f"{_MES_PT[m.month]}/{m.year}" for m in meses_list]
        try:
            default_idx = next(i for i, m in enumerate(meses_list) if m.year == 2026 and m.month == 5)
        except StopIteration:
            default_idx = 0
        fmes1, fmes2, fmes3 = st.columns([2, 2, 4])
        with fmes1:
            mes_idx = st.selectbox("Mês de referência", range(len(meses_list)),
                                   index=default_idx,
                                   format_func=lambda i: labels_mes[i],
                                   key="lider_mes")
        with fmes2:
            incluir_mkt = st.toggle("Incluir Marketplace", value=True, key="lider_inc_mkt",
                                    help="O Marketplace (e-commerce) tem milhares de micro-pedidos que "
                                         "distorcem o ticket médio e a contagem de transações. Desligue "
                                         "para ver só o comercial B2B (Hospitalar/Farmácias/SAC).")
        mes_ref = meses_list[mes_idx]
        mes_ant = (pd.Timestamp(mes_ref) - pd.offsets.MonthBegin(1)).date()
        # Mesmo mês ano anterior (YoY)
        mes_ano_ant = pd.Timestamp(mes_ref).replace(year=mes_ref.year - 1).date()

        # Metodologia OFICIAL Alves (validada 03/06/2026):
        # canal classificado por YGRUVEN do vendedor da venda — mesma regra do BI dele.
        # Marketplace = EC (e-commerce) + vendas sem vendedor (NULL = canais MKT).
        carteira_join = ""  # carteira não é mais necessária pra classificar canal aqui

        canal_case = """
        CASE
          WHEN o.salesperson_group_code = 'FA' THEN 'Hospitalar'
          WHEN o.salesperson_group_code = 'FR' THEN 'Farmácias'
          WHEN o.salesperson_group_code = 'PC' THEN 'SAC'
          WHEN o.salesperson_group_code = 'EC' OR o.salesperson_group_code IS NULL THEN 'Marketplace'
          ELSE 'Outros'
        END
        """

        # Query: mês selecionado + mês anterior + mesmo mês ano anterior
        # Metodologia OFICIAL Alves: JOIN dim_operation_nature filtrando financial_flag<>'N',
        # janela por invoice_date, valor = product_amount (yValPro)
        try:
            df_lider = query(f"""
              SELECT
                {canal_case} AS canal,
                DATE_TRUNC(o.invoice_date, MONTH) AS mes,
                DATE_TRUNC(o.invoice_date, WEEK(MONDAY)) AS semana,
                o.order_number, o.invoice_date, o.product_amount
              FROM `{ORDERS}.fact_sales_order` o
              JOIN `{ORDERS}.dim_operation_nature` n
                ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
              {carteira_join}
              WHERE (
                  DATE_TRUNC(o.invoice_date, MONTH) IN (
                      DATE('{mes_ref}'),
                      DATE('{mes_ant}'),
                      DATE('{mes_ano_ant}')
                  )
                )
                AND o.invoice_date IS NOT NULL
            """)
        except Exception as e:
            st.error(f"Erro consultando fact_sales_order: {e}")
            df_lider = pd.DataFrame()

        if df_lider.empty:
            st.warning("Sem dados para o mês selecionado.")
        else:
            df_lider["invoice_date"] = pd.to_datetime(df_lider["invoice_date"])
            df_lider["mes"] = pd.to_datetime(df_lider["mes"]).dt.date
            df_lider["semana"] = pd.to_datetime(df_lider["semana"]).dt.date
            df_lider["product_amount"] = pd.to_numeric(df_lider["product_amount"], errors="coerce").fillna(0.0)

            df_mes  = df_lider[df_lider["mes"] == mes_ref]
            df_ant  = df_lider[df_lider["mes"] == mes_ant]
            df_yoy  = df_lider[df_lider["mes"] == mes_ano_ant]
            # Toggle: sem Marketplace → visão comercial B2B (ticket médio não distorcido)
            if not incluir_mkt:
                df_mes = df_mes[df_mes["canal"] != "Marketplace"]
                df_ant = df_ant[df_ant["canal"] != "Marketplace"]
                df_yoy = df_yoy[df_yoy["canal"] != "Marketplace"]

            fat_mes = float(df_mes["product_amount"].sum())
            fat_ant = float(df_ant["product_amount"].sum())
            fat_yoy = float(df_yoy["product_amount"].sum())
            trans_mes = len(df_mes)  # contagem de notas (não distinct order_number) — alinhado com COUNT(*) do Alves
            ticket = fat_mes / trans_mes if trans_mes else 0
            var_mom = ((fat_mes - fat_ant) / fat_ant * 100) if fat_ant else 0
            var_yoy = ((fat_mes - fat_yoy) / fat_yoy * 100) if fat_yoy else 0

            yoy_label = f"vs {_MES_PT[mes_ano_ant.month]}/{mes_ano_ant.year}"

            # Projeção (Vinícius 26/06): onde a equipe DEVERIA estar HOJE para bater a meta
            # = meta mensal ÷ dias úteis × dias úteis já decorridos. Substitui "Transações"
            # e vai como 1º card. No mês corrente usa hoje; em mês fechado usa o fim do mês
            # (projeção = meta cheia → % atingido vira % da meta do mês).
            hoje_ = pd.Timestamp.today().date()
            if mes_ref.year == hoje_.year and mes_ref.month == hoje_.month:
                ref_proj = hoje_
            else:
                ref_proj = (pd.Timestamp(mes_ref) + pd.offsets.MonthEnd(0)).date()
            meta_geral_mes = metas_store.meta_do_mes("GERAL", mes_ref)
            proj_esperada = gv.projecao_esperada(meta_geral_mes, ref_proj)
            pct_proj = (fat_mes / proj_esperada) if proj_esperada else 0.0

            kpi_row([
                {"label": "Projeção (esperado até hoje)", "value": fmt_brl(proj_esperada),
                 "delta": f"{pct_proj*100:.0f}% atingido",
                 "delta_dir": "up" if fat_mes >= proj_esperada else "down"},
                {"label": "Faturamento", "value": fmt_brl(fat_mes), "variant": "success"},
                {"label": "vs Mês Anterior", "value": fmt_brl(fat_ant),
                 "delta": fmt_pct(var_mom), "delta_dir": "up" if var_mom >= 0 else "down"},
                {"label": yoy_label,
                 "value": fmt_brl(fat_yoy) if fat_yoy else "—",
                 "delta": fmt_pct(var_yoy) if fat_yoy else "",
                 "delta_dir": "up" if var_yoy >= 0 else "down"},
                {"label": "Ticket Médio", "value": fmt_brl(ticket)},
            ])
            st.caption("Projeção = meta mensal ÷ dias úteis × dias úteis decorridos "
                       "(onde a equipe deveria estar hoje para bater a meta).")

            st.markdown("<br>", unsafe_allow_html=True)

            # Breakdown por canal — só mostra faturamento + comparativos (sem meta)
            ag_canal_mes = df_mes.groupby("canal").agg(
                faturamento=("product_amount", "sum"),
                transacoes=("order_number", "count"),  # COUNT(*) alinhado c/ metodologia Alves
            ).reset_index()
            ag_canal_ant = df_ant.groupby("canal")["product_amount"].sum().rename("fat_mes_ant").reset_index()
            ag_canal_yoy = df_yoy.groupby("canal")["product_amount"].sum().rename("fat_yoy").reset_index()
            ag_canal = ag_canal_mes.merge(ag_canal_ant, on="canal", how="left").merge(ag_canal_yoy, on="canal", how="left")
            ag_canal["fat_mes_ant"] = ag_canal["fat_mes_ant"].fillna(0)
            ag_canal["fat_yoy"]     = ag_canal["fat_yoy"].fillna(0)
            ag_canal["var_mom"]     = ((ag_canal["faturamento"] - ag_canal["fat_mes_ant"]) /
                                       ag_canal["fat_mes_ant"].replace(0, pd.NA)) * 100
            ag_canal["var_yoy"]     = ((ag_canal["faturamento"] - ag_canal["fat_yoy"]) /
                                       ag_canal["fat_yoy"].replace(0, pd.NA)) * 100
            ag_canal["ticket"]      = ag_canal["faturamento"] / ag_canal["transacoes"]
            ordem_canal = ["Hospitalar", "Marketplace", "Farmácias", "SAC", "Outros"]
            ag_canal["__ord"] = ag_canal["canal"].map({c: i for i, c in enumerate(ordem_canal)}).fillna(99)
            ag_canal = ag_canal.sort_values("__ord").drop(columns="__ord")

            colg1, colg2 = st.columns([3, 2])
            with colg1:
                df_plot = ag_canal[["canal", "faturamento", "fat_mes_ant", "fat_yoy"]].rename(columns={
                    "faturamento": f"{_MES_PT[mes_ref.month]}/{mes_ref.year}",
                    "fat_mes_ant": f"{_MES_PT[mes_ant.month]}/{mes_ant.year}",
                    "fat_yoy":     f"{_MES_PT[mes_ano_ant.month]}/{mes_ano_ant.year}",
                })
                df_melt = df_plot.melt(id_vars="canal", var_name="período", value_name="R$")
                # Label dos valores nas barras (formato BR: R$ X.XXXk ou R$ X,XXM)
                def _fmt_compact(v):
                    if v >= 1_000_000:
                        return f"R$ {v/1_000_000:.2f}M".replace(".", ",")
                    if v >= 1_000:
                        return f"R$ {v/1_000:.0f}k"
                    return f"R$ {v:.0f}"
                df_melt["label"] = df_melt["R$"].apply(_fmt_compact)
                fig_can = px.bar(
                    df_melt,
                    x="canal", y="R$", color="período", barmode="group",
                    text="label",
                    title="Faturamento por Canal — comparativo dos 3 períodos",
                    color_discrete_sequence=["#1E1882", "#7A7AC8", "#B8B6E0"],
                )
                fig_can.update_traces(textposition="outside", textfont_size=11, cliponaxis=False)
                fig_can.update_layout(
                    plot_bgcolor="white", paper_bgcolor="white",
                    legend_title_text="",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(t=70, b=40, l=40, r=20),
                    yaxis_title="Faturamento (R$)",
                    xaxis_title="",
                )
                st.plotly_chart(fig_can, use_container_width=True)
            with colg2:
                # Cards por canal — mais limpo que tabela, alinhado com paleta Nevoni.
                CANAL_VISUAL = {
                    "Hospitalar":  {"emoji": "", "cor": "#0D2B6B"},
                    "Marketplace": {"emoji": "", "cor": "#0D8B92"},
                    "Farmácias":   {"emoji": "", "cor": "#7030A0"},
                    "SAC":         {"emoji": "", "cor": "#C55A11"},
                    "Outros":      {"emoji": "", "cor": "#6B7280"},
                }
                cards_html = []
                for _, r in ag_canal.iterrows():
                    vis = CANAL_VISUAL.get(r["canal"], CANAL_VISUAL["Outros"])
                    fat = fmt_brl(float(r["faturamento"]))
                    trans = f'{int(r["transacoes"]):,}'.replace(",", ".")
                    tkt = fmt_brl(float(r["ticket"])) if pd.notna(r["ticket"]) else "—"
                    # MoM
                    mom_val = r["var_mom"]
                    if pd.notna(mom_val):
                        mom_arrow = "▲" if mom_val >= 0 else "▼"
                        mom_color = "#16A34A" if mom_val >= 0 else "#DC2626"
                        mom_html = f'<span style="color:{mom_color};font-weight:600">{mom_arrow} {abs(mom_val):.1f}%</span>'
                    else:
                        mom_html = '<span style="color:#9CA3AF">—</span>'
                    # YoY
                    yoy_val = r["var_yoy"]
                    if pd.notna(yoy_val):
                        yoy_arrow = "▲" if yoy_val >= 0 else "▼"
                        yoy_color = "#16A34A" if yoy_val >= 0 else "#DC2626"
                        yoy_html = f'<span style="color:{yoy_color};font-weight:600">{yoy_arrow} {abs(yoy_val):.1f}%</span>'
                    else:
                        yoy_html = '<span style="color:#9CA3AF">—</span>'

                    cards_html.append(f"""
                    <div style="
                        background:#FFFFFF;
                        border:1px solid #E5E7EB;
                        border-left:4px solid {vis['cor']};
                        border-radius:10px;
                        padding:14px 18px;
                        margin-bottom:12px;
                        box-shadow:0 1px 2px rgba(0,0,0,0.04);">
                      <div style="display:flex;justify-content:space-between;align-items:baseline;">
                        <div style="font-size:13px;font-weight:700;color:#111827;text-transform:uppercase;letter-spacing:0.4px;">
                          <span style="font-size:16px;margin-right:6px;">{vis['emoji']}</span>{r['canal']}
                        </div>
                        <div style="text-align:right;">
                          <div style="font-size:20px;font-weight:800;color:{vis['cor']};line-height:1.1;">{fat}</div>
                          <div style="font-size:10px;color:#9CA3AF;margin-top:2px;letter-spacing:0.3px;">
                            referência: {_MES_PT[mes_ref.month]}/{mes_ref.year}
                          </div>
                        </div>
                      </div>
                      <div style="display:flex;gap:18px;margin-top:8px;font-size:12px;color:#6B7280;">
                        <span>MoM {mom_html}</span>
                        <span>YoY {yoy_html}</span>
                      </div>
                      <div style="display:flex;gap:18px;margin-top:4px;font-size:12px;color:#6B7280;">
                        <span><b>{trans}</b> transações</span>
                        <span>ticket <b>{tkt}</b></span>
                      </div>
                    </div>
                    """)
                st.markdown("".join(cards_html), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Evolução mensal por canal — últimos 12 meses ─────────────
            # Sugestão Vini: "mostrar os meses individuais no gráfico"
            try:
                mes_inicio_evol = (pd.Timestamp(mes_ref) - pd.offsets.MonthBegin(11)).date()
                # mes_ref é o 1º dia do mês — fim do mês é o último dia
                mes_fim_evol    = (pd.Timestamp(mes_ref) + pd.offsets.MonthEnd(0)).date()
                df_evol = query(f"""
                  SELECT
                    DATE_TRUNC(o.invoice_date, MONTH) AS mes,
                    CASE
                      WHEN o.salesperson_group_code = 'FA' THEN 'Hospitalar'
                      WHEN o.salesperson_group_code = 'FR' THEN 'Farmácias'
                      WHEN o.salesperson_group_code = 'PC' THEN 'SAC'
                      WHEN o.salesperson_group_code = 'EC' OR o.salesperson_group_code IS NULL THEN 'Marketplace'
                      ELSE 'Outros'
                    END AS canal,
                    SUM(o.product_amount) AS faturamento
                  FROM `{ORDERS}.fact_sales_order` o
                  JOIN `{ORDERS}.dim_operation_nature` n
                    ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
                  WHERE o.invoice_date BETWEEN DATE('{mes_inicio_evol}') AND DATE('{mes_fim_evol}')
                    AND o.invoice_date IS NOT NULL
                  GROUP BY mes, canal
                  ORDER BY mes, canal
                """)
            except Exception as e:
                df_evol = pd.DataFrame()
                st.warning(f"Não foi possível carregar evolução mensal: {e}")

            if not df_evol.empty:
                df_evol["mes"] = pd.to_datetime(df_evol["mes"])
                df_evol["mes_label"] = df_evol["mes"].dt.strftime("%b/%y").str.capitalize()
                df_evol["faturamento"] = pd.to_numeric(df_evol["faturamento"], errors="coerce").fillna(0)
                ordem_mes = df_evol.sort_values("mes")["mes_label"].drop_duplicates().tolist()
                fig_evol = px.bar(
                    df_evol,
                    x="mes_label", y="faturamento", color="canal",
                    barmode="group",
                    title=f"Evolução Mensal por Canal — últimos 12 meses",
                    labels={"mes_label": "Mês", "faturamento": "Faturamento (R$)", "canal": "Canal"},
                    category_orders={"mes_label": ordem_mes,
                                     "canal": ["Hospitalar", "Marketplace", "Farmácias", "SAC", "Outros"]},
                    color_discrete_map={
                        "Hospitalar": "#0D2B6B", "Marketplace": "#0D8B92",
                        "Farmácias": "#7030A0", "SAC": "#C55A11", "Outros": "#6B7280",
                    },
                )
                fig_evol.update_layout(
                    plot_bgcolor="white", paper_bgcolor="white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(t=70, b=40, l=40, r=20),
                    legend_title_text="",
                )
                st.plotly_chart(fig_evol, use_container_width=True)

                # Tabela compacta também — soma total por mês (sem quebrar canal)
                df_total_mes = df_evol.groupby(["mes", "mes_label"], as_index=False)["faturamento"].sum().sort_values("mes")
                df_total_mes["faturamento_fmt"] = df_total_mes["faturamento"].apply(fmt_brl)
                df_total_mes["MoM"] = df_total_mes["faturamento"].pct_change() * 100
                df_total_mes["MoM"] = df_total_mes["MoM"].apply(lambda v: fmt_pct(v) if pd.notna(v) else "—")
                df_show = df_total_mes[["mes_label", "faturamento_fmt", "MoM"]].copy()
                df_show.columns = ["Mês", "Faturamento Total", "Δ MoM"]
                with st.expander("Detalhamento mensal (total)", expanded=False):
                    st.dataframe(df_show, hide_index=True, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # View semanal — semana DO MÊS (dia 1-7, 8-14, 15-21, 22-28, 29-31)
            # Evita o bug de "Sem 4 (27/04)" aparecendo em Maio porque a segunda
            # da semana caía em Abril mas as vendas eram de 01-03/05.
            df_mes_w = df_mes.copy()
            df_mes_w["semana_mes"] = ((df_mes_w["invoice_date"].dt.day - 1) // 7) + 1
            ag_sem = df_mes_w.groupby(["semana_mes", "canal"]).agg(
                faturamento=("product_amount", "sum"),
            ).reset_index()
            # Range de dias da semana
            def _range_label(n):
                inicio = (n - 1) * 7 + 1
                # último dia do mês de referência
                import calendar
                ultimo = calendar.monthrange(mes_ref.year, mes_ref.month)[1]
                fim = min(n * 7, ultimo)
                return f"Sem {n} ({inicio:02d}-{fim:02d}/{mes_ref.month:02d})"
            ag_sem["semana_label"] = ag_sem["semana_mes"].apply(_range_label)

            fig_sem = px.bar(
                ag_sem.sort_values(["semana_mes", "canal"]),
                x="semana_label", y="faturamento", color="canal",
                title=f"Faturamento Semanal por Canal — {_MES_PT[mes_ref.month]}/{mes_ref.year}",
                labels={"semana_label": "Semana", "faturamento": "R$", "canal": "Canal"},
                color_discrete_map={
                    "Hospitalar": "#0D2B6B", "Marketplace": "#0D8B92",
                    "Farmácias": "#7030A0", "SAC": "#FFC000", "Outros": "#95A5C1",
                },
            )
            fig_sem.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_sem, use_container_width=True)

            # Tabela semanal totais — ordenada por semana do mês
            tot_sem = ag_sem.groupby(["semana_mes", "semana_label"], as_index=False)["faturamento"].sum()
            tot_sem = tot_sem.sort_values("semana_mes").drop(columns="semana_mes")
            media_sem = float(tot_sem["faturamento"].mean()) if len(tot_sem) else 0
            # Variação real vs média (com sinal + ou -, intuitivo)
            tot_sem["vs média"] = ((tot_sem["faturamento"] - media_sem) / media_sem * 100).apply(fmt_pct) if media_sem else "—"
            tot_sem["faturamento"] = tot_sem["faturamento"].apply(fmt_brl)
            tot_sem.columns = ["Semana", "Faturamento", "vs média semanal"]
            st.dataframe(tot_sem, hide_index=True, use_container_width=True)

    # ═══ Consulta por período exato (pedido Alves 09/06) ══════════════════
    st.markdown("---")
    section_title("Faturamento por Período Exato")
    st.caption("Escolha um intervalo de datas (ex: semana passada, dia 15 ao 20). "
               "Mesma metodologia validada — faturamento por data da nota (yValPro).")
    try:
        _maxd = pd.to_datetime(query(
            f"SELECT MAX(invoice_date) AS d FROM `{ORDERS}.fact_sales_order` WHERE invoice_date IS NOT NULL"
        )["d"].iloc[0]).date()
    except Exception:
        _maxd = pd.Timestamp.now().date()
    _ini_default = (pd.Timestamp(_maxd) - pd.Timedelta(days=7)).date()
    pc1, pc2, _pc3 = st.columns([2, 2, 4])
    with pc1:
        dt_ini = st.date_input("De", value=_ini_default, key="vendas_dt_ini", format="DD/MM/YYYY")
    with pc2:
        dt_fim = st.date_input("Até", value=_maxd, key="vendas_dt_fim", format="DD/MM/YYYY")
    if dt_ini > dt_fim:
        st.warning("A data inicial não pode ser maior que a final.")
    else:
        df_per = query(f"""
            SELECT
              CASE
                WHEN o.salesperson_group_code = 'FA' THEN 'Hospitalar'
                WHEN o.salesperson_group_code = 'FR' THEN 'Farmácias'
                WHEN o.salesperson_group_code = 'PC' THEN 'SAC'
                WHEN o.salesperson_group_code = 'EC' OR o.salesperson_group_code IS NULL THEN 'Marketplace'
                ELSE 'Outros' END                      AS canal,
              COUNT(*)                                 AS pedidos,
              SUM(o.product_amount)                    AS faturamento
            FROM `{ORDERS}.fact_sales_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            WHERE o.invoice_date BETWEEN '{dt_ini}' AND '{dt_fim}'
            GROUP BY 1 ORDER BY faturamento DESC
        """)
        if df_per.empty:
            st.info("Sem faturamento nesse período.")
        else:
            df_per["faturamento"] = pd.to_numeric(df_per["faturamento"], errors="coerce").fillna(0)
            df_per["pedidos"] = pd.to_numeric(df_per["pedidos"], errors="coerce").fillna(0).astype(int)
            tot_fat = float(df_per["faturamento"].sum())
            tot_ped = int(df_per["pedidos"].sum())
            pk1, pk2, pk3 = st.columns(3)
            with pk1: kpi_card("Faturamento no período", fmt_brl(tot_fat))
            with pk2: kpi_card("Pedidos", f"{tot_ped:,}".replace(",", "."))
            with pk3: kpi_card("Ticket médio", fmt_brl(tot_fat / tot_ped if tot_ped else 0))
            df_show_per = df_per.copy()
            df_show_per["faturamento"] = df_show_per["faturamento"].apply(fmt_brl)
            df_show_per.columns = ["Canal", "Pedidos", "Faturamento"]
            st.dataframe(df_show_per, hide_index=True, use_container_width=True)

    # ═══ Calendário de Vendas Diárias (reunião 26/06, Vinícius) ════════════
    st.markdown("---")
    calendario_view.render_calendario(mes_ref, key_prefix="vendas_cal")
    calendario_view.render_faturamento_mensal()

# ── Compras ──────────────────────────────────────────────────
with tab_compra:
    section_title("Compras e Suprimentos")
    st.caption("A Nevoni FABRICA: compra insumos/componentes e monta o equipamento médico. "
               "São dois canais — mercadoria doméstica e importação (China). A razão compra/venda "
               "de ~24% (doméstico) reflete a margem de manufatura, não um erro de dado.")

    dom = query(f"""
        SELECT COUNT(*) AS ordens, SUM(o.product_amount) AS valor
        FROM `{ORDERS}.fact_purchase_order` o
        JOIN `{ORDERS}.dim_operation_nature` n ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
        WHERE o.invoice_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH) AND o.excluded_at IS NULL
    """)
    imp = query(f"""
        WITH s AS (
            SELECT supplier_name, SUM(total_brl) AS v
            FROM `{PROJ}.dm_imports.fact_import_order` WHERE excluded_at IS NULL GROUP BY 1
        )
        SELECT (SELECT SUM(v) FROM s) AS total_v,
               (SELECT SUM(total_usd) FROM `{PROJ}.dm_imports.fact_import_order` WHERE excluded_at IS NULL) AS usd,
               (SELECT v FROM s ORDER BY v DESC LIMIT 1) AS top_v,
               (SELECT supplier_name FROM s ORDER BY v DESC LIMIT 1) AS top_name
    """)
    ven = query(f"""
        SELECT SUM(o.product_amount) AS v
        FROM `{ORDERS}.fact_sales_order` o
        JOIN `{ORDERS}.dim_operation_nature` n ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
        WHERE o.invoice_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    """)
    dom_val = float(pd.to_numeric(dom["valor"].iloc[0], errors="coerce")) if not dom.empty and pd.notna(dom["valor"].iloc[0]) else 0.0
    ven_val = float(pd.to_numeric(ven["v"].iloc[0], errors="coerce")) if not ven.empty and pd.notna(ven["v"].iloc[0]) else 0.0
    imp_brl = float(pd.to_numeric(imp["total_v"].iloc[0], errors="coerce")) if not imp.empty and pd.notna(imp["total_v"].iloc[0]) else 0.0
    imp_usd = float(pd.to_numeric(imp["usd"].iloc[0], errors="coerce")) if not imp.empty and pd.notna(imp["usd"].iloc[0]) else 0.0
    top_v = float(pd.to_numeric(imp["top_v"].iloc[0], errors="coerce")) if not imp.empty and pd.notna(imp["top_v"].iloc[0]) else 0.0
    top_name = str(imp["top_name"].iloc[0]) if not imp.empty and pd.notna(imp["top_name"].iloc[0]) else ""
    conc = (top_v / imp_brl * 100) if imp_brl else 0
    razao = (dom_val / ven_val * 100) if ven_val else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: kpi_card("Compras Mercadoria (12m)", fmt_brl(dom_val), delta="doméstico", delta_dir="flat", variant="warning")
    with k2: kpi_card("Importação (acumulado)", fmt_brl(imp_brl),
                      delta=("US$ " + f"{imp_usd:,.0f}".replace(",", ".")), delta_dir="flat")
    with k3: kpi_card("Razão Compra/Venda", f"{razao:.1f}%", delta="margem de manufatura saudável", delta_dir="flat", variant="success")
    with k4: kpi_card("Concentração Import", f"{conc:.0f}%",
                      delta=(top_name[:20] + " (fornecedor único)"), delta_dir="down", variant="danger")

    st.markdown("<br>", unsafe_allow_html=True)
    c_mes, c_imp = st.columns(2)
    with c_mes:
        df_cv = query(f"""
            WITH v AS (
              SELECT DATE_TRUNC(o.invoice_date, MONTH) AS mes, SUM(o.product_amount) AS vendas
              FROM `{ORDERS}.fact_sales_order` o
              JOIN `{ORDERS}.dim_operation_nature` n ON n.nature_code=o.nature_code AND n.financial_flag<>'N'
              WHERE o.invoice_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 12 MONTH)
                AND o.invoice_date < DATE_TRUNC(CURRENT_DATE(), MONTH) GROUP BY 1),
            c AS (
              SELECT DATE_TRUNC(o.invoice_date, MONTH) AS mes, SUM(o.product_amount) AS compras
              FROM `{ORDERS}.fact_purchase_order` o
              JOIN `{ORDERS}.dim_operation_nature` n ON n.nature_code=o.nature_code AND n.financial_flag<>'N'
              WHERE o.invoice_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 12 MONTH)
                AND o.invoice_date < DATE_TRUNC(CURRENT_DATE(), MONTH) AND o.excluded_at IS NULL GROUP BY 1)
            SELECT v.mes, v.vendas, COALESCE(c.compras, 0) AS compras
            FROM v LEFT JOIN c USING(mes) ORDER BY v.mes
        """)
        if not df_cv.empty:
            df_cv["mes"] = pd.to_datetime(df_cv["mes"])
            df_cv["vendas"] = pd.to_numeric(df_cv["vendas"], errors="coerce").fillna(0)
            df_cv["compras"] = pd.to_numeric(df_cv["compras"], errors="coerce").fillna(0)
            fig_cv = go.Figure()
            fig_cv.add_trace(go.Bar(x=df_cv["mes"], y=df_cv["vendas"], name="Vendas", marker_color="#16A34A"))
            fig_cv.add_trace(go.Bar(x=df_cv["mes"], y=df_cv["compras"], name="Compras", marker_color="#4844C8"))
            fig_cv.update_layout(title=dict(text="Vendas vs Compras por Mês", x=0, xanchor="left"),
                                 barmode="group", plot_bgcolor="white", paper_bgcolor="white",
                                 legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
                                 margin=dict(t=66, b=8))
            st.plotly_chart(fig_cv, use_container_width=True)
    with c_imp:
        df_imp = query(f"""
            SELECT supplier_name, ROUND(SUM(total_brl), 0) AS valor
            FROM `{PROJ}.dm_imports.fact_import_order` WHERE excluded_at IS NULL
            GROUP BY 1 ORDER BY valor DESC LIMIT 8
        """)
        if not df_imp.empty:
            df_imp["valor"] = pd.to_numeric(df_imp["valor"], errors="coerce").fillna(0)
            df_imp["supplier_name"] = df_imp["supplier_name"].astype(str).str.slice(0, 26)
            fig_imp = px.bar(df_imp, x="valor", y="supplier_name", orientation="h",
                             title="Importação por Fornecedor (R$) — concentração",
                             labels={"valor": "R$", "supplier_name": ""},
                             color_discrete_sequence=["#991B1B"])
            fig_imp.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                  yaxis=dict(autorange="reversed"), margin=dict(t=44, l=8, r=8))
            st.plotly_chart(fig_imp, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    section_title("Top Fornecedores — Mercadoria Doméstica (12m)")
    df_forn = query(f"""
        SELECT p.partner_name AS fornecedor, COUNT(*) AS ordens, ROUND(SUM(o.product_amount), 2) AS valor
        FROM `{ORDERS}.fact_purchase_order` o
        JOIN `{ORDERS}.dim_operation_nature` n ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
        LEFT JOIN `{PROJ}.dm_partners.dim_partner` p USING (partner_code)
        WHERE o.invoice_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH) AND o.excluded_at IS NULL
        GROUP BY 1 ORDER BY valor DESC LIMIT 10
    """)
    if not df_forn.empty:
        df_forn["valor"] = pd.to_numeric(df_forn["valor"], errors="coerce").fillna(0).apply(fmt_brl)
        df_forn["ordens"] = pd.to_numeric(df_forn["ordens"], errors="coerce").fillna(0).astype(int)
        df_forn.columns = ["Fornecedor", "Ordens", "Valor"]
        st.dataframe(df_forn, hide_index=True, use_container_width=True)

# ── Orçamentos ───────────────────────────────────────────────
with tab_orc:
    section_title("Orçamentos — Pipeline e Conversão")
    st.caption("Orçamento cobre PARTE do funil: Farmácias não orça (manda proposta direto) e "
               "Hospitalar/SAC às vezes recebem a ordem de compra pronta. Ciclo de venda mediano ≈ 3 dias — "
               "orçamento que não fecha em ~1 semana está parado. Janela: últimos 12 meses (data de criação no ERP).")

    df_okpi = query(f"""
        SELECT
          ROUND(SUM(IF(detailed_status=1 AND created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY), total_amount, 0)),2)  AS pipe,
          COUNTIF(detailed_status=1 AND created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY))                            AS pipe_n,
          ROUND(SUM(IF(detailed_status=1 AND created_at_erp<TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 180 DAY), total_amount, 0)),2) AS parado,
          COUNTIF(detailed_status=1 AND created_at_erp<TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 180 DAY))                           AS parado_n,
          ROUND(SAFE_DIVIDE(
            COUNTIF(detailed_status=2 AND created_at_erp<=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY)),
            COUNTIF(created_at_erp<=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY)))*100, 1)                                      AS conv
        FROM `{QUOTES}.fact_quote`
        WHERE excluded_at IS NULL AND created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
    """)
    df_cic = query(f"""
        SELECT CAST(APPROX_QUANTILES(DATE_DIFF(o.invoice_date, DATE(q.created_at_erp), DAY), 2)[OFFSET(1)] AS INT64) AS ciclo
        FROM `{QUOTES}.fact_quote` q
        JOIN `{ORDERS}.fact_sales_order` o ON o.quote_number = q.quote_number
        WHERE q.created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
          AND o.invoice_date >= DATE(q.created_at_erp) AND o.invoice_date IS NOT NULL
    """)
    if df_okpi.empty:
        st.info("Sem orçamentos no período.")
    else:
        r0 = df_okpi.iloc[0]
        ciclo = int(df_cic.iloc[0]["ciclo"]) if (not df_cic.empty and pd.notna(df_cic.iloc[0]["ciclo"])) else 0
        k1, k2, k3, k4 = st.columns(4)
        with k1: kpi_card("Pipeline Vivo (≤90d)", fmt_brl(float(r0["pipe"])),
                          delta=f'{int(r0["pipe_n"])} orçamentos abertos', delta_dir="flat", variant="success")
        with k2: kpi_card("Conversão (safra madura)", f'{float(r0["conv"]):.1f}%',
                          delta="orçamentos com tempo de fechar", delta_dir="flat")
        with k3: kpi_card("Ciclo de venda (mediana)", f"{ciclo} dias",
                          delta="do orçamento ao faturamento", delta_dir="flat")
        with k4: kpi_card("Parados +180d", fmt_brl(float(r0["parado"])),
                          delta=f'{int(r0["parado_n"])} p/ recuperar ou encerrar', delta_dir="down", variant="danger")

        st.markdown("<br>", unsafe_allow_html=True)
        c_safra, c_idade = st.columns(2)
        with c_safra:
            df_safra = query(f"""
                SELECT FORMAT_DATE('%b/%y', DATE(created_at_erp)) AS mes,
                       DATE_TRUNC(DATE(created_at_erp), MONTH)     AS ord,
                       ROUND(SAFE_DIVIDE(COUNTIF(detailed_status=2), COUNT(*))*100, 1) AS conv
                FROM `{QUOTES}.fact_quote`
                WHERE excluded_at IS NULL AND created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
                GROUP BY 1, 2 ORDER BY ord
            """)
            if not df_safra.empty:
                df_safra["conv"] = pd.to_numeric(df_safra["conv"], errors="coerce").fillna(0)
                fig_s = px.bar(df_safra, x="mes", y="conv", title="Conversão por Safra (%) — safras recentes ainda fechando",
                               labels={"mes": "", "conv": "%"}, color_discrete_sequence=["#16A34A"])
                fig_s.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=44, b=8))
                st.plotly_chart(fig_s, use_container_width=True)
        with c_idade:
            df_idade = query(f"""
                SELECT CASE
                    WHEN created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 30 DAY)  THEN '1. ate 30d (quente)'
                    WHEN created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY)  THEN '2. 31-90d'
                    WHEN created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 180 DAY) THEN '3. 91-180d'
                    ELSE '4. +180d (morto)' END                  AS idade,
                    ROUND(SUM(total_amount), 0)                  AS valor
                FROM `{QUOTES}.fact_quote`
                WHERE excluded_at IS NULL AND detailed_status=1
                  AND created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
                GROUP BY 1 ORDER BY 1
            """)
            if not df_idade.empty:
                df_idade["valor"] = pd.to_numeric(df_idade["valor"], errors="coerce").fillna(0)
                fig_i = px.bar(df_idade, x="idade", y="valor", title="Orçamentos em Aberto por Idade (R$)",
                               labels={"idade": "", "valor": "R$"}, color="idade",
                               color_discrete_map={'1. ate 30d (quente)':'#16A34A','2. 31-90d':'#A3D977',
                                                   '3. 91-180d':'#FCD34D','4. +180d (morto)':'#991B1B'})
                fig_i.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=44, b=8), showlegend=False)
                st.plotly_chart(fig_i, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        section_title("Orçamentos Parados +180 dias — Recuperar ou Encerrar")
        st.caption("Com ciclo de venda de ~3 dias, orçamento aberto há +180 dias está morto. "
                   "Lista pra o time decidir: retomar o contato ou dar baixa (limpa o pipeline).")
        df_parados = query(f"""
            SELECT COALESCE(p.partner_name, CAST(q.partner_code AS STRING))   AS cliente,
                   DATE_DIFF(CURRENT_DATE(), DATE(q.created_at_erp), DAY)      AS dias_parado,
                   q.total_amount                                             AS valor
            FROM `{QUOTES}.fact_quote` q
            LEFT JOIN `{PROJ}.dm_partners.dim_partner` p USING (partner_code)
            WHERE q.excluded_at IS NULL AND q.detailed_status=1
              AND q.created_at_erp <  TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
              AND q.created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
            ORDER BY q.total_amount DESC LIMIT 20
        """)
        if not df_parados.empty:
            df_parados["valor"] = pd.to_numeric(df_parados["valor"], errors="coerce").fillna(0).apply(fmt_brl)
            df_parados["dias_parado"] = pd.to_numeric(df_parados["dias_parado"], errors="coerce").fillna(0).astype(int)
            df_parados.columns = ["Cliente", "Dias parado", "Valor"]
            st.dataframe(df_parados, hide_index=True, use_container_width=True)

# ── CRM Funil ────────────────────────────────────────────────
with tab_crm:
    section_title("Funil de Vendas CRM — Pipedrive")

    CRM = f"{PROJ}.crm_raw"

    # 3 pipelines reais no Pipedrive da Nevoni
    PIPELINES = {
        "Funil Vendas Farmácia":     f"{CRM}.funil_vendas_farmacia",
        "Recorrência Farmácia":      f"{CRM}.recorrencia_farmacia",
        "Recorrência Distribuidores": f"{CRM}.recorrencia_distribuidores",
    }

    PERIODOS_CRM = {"Tudo": None, "Últimos 3 meses": 3, "Últimos 6 meses": 6, "Últimos 12 meses": 12}
    fcrm1, fcrm2, fcrm3 = st.columns([2, 2, 4])
    with fcrm1:
        pipeline_sel = st.selectbox("Pipeline", ["TODOS"] + list(PIPELINES.keys()),
                                    key="crm_pipeline")
    with fcrm2:
        periodo_crm = st.selectbox("Período (criação do deal)", list(PERIODOS_CRM.keys()),
                                   index=0, key="crm_periodo")

    union_sql = "\n  UNION ALL\n".join([
        f"SELECT '{nome}' AS pipeline_nome, deal_id, title, value, status, "
        f"stage_id, owner_id, local_close_date, local_won_date, local_lost_date, "
        f"DATE(add_time) AS data_criacao "
        f"FROM `{tbl}` WHERE is_deleted IS NOT TRUE"
        for nome, tbl in PIPELINES.items()
    ])
    _conds = []
    if pipeline_sel != "TODOS":
        _conds.append(f"pipeline_nome = '{pipeline_sel}'")
    _meses_crm = PERIODOS_CRM[periodo_crm]
    if _meses_crm:
        _conds.append(f"data_criacao >= DATE_SUB(CURRENT_DATE(), INTERVAL {_meses_crm} MONTH)")
    where_pip = ("WHERE " + " AND ".join(_conds)) if _conds else ""

    try:
        df = query(f"""
            WITH deals AS (
              {union_sql}
            )
            SELECT
              d.pipeline_nome,
              d.deal_id,
              d.title,
              d.value,
              d.status,
              s.stage_name,
              s.order_nr AS stage_order,
              u.name AS owner_nome,
              d.local_close_date,
              d.local_won_date,
              d.local_lost_date
            FROM deals d
            LEFT JOIN `{CRM}.dim_crm_stage` s ON s.stage_id = d.stage_id
            LEFT JOIN `{CRM}.dim_crm_user`  u ON u.user_id  = d.owner_id
            {where_pip}
        """)
    except Exception as e:
        st.error(f"Erro ao consultar CRM: {e}")
        df = pd.DataFrame()

    if df.empty:
        st.info("Sem deals no CRM para o filtro selecionado.")
    else:
        df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0.0)
        total      = len(df)
        ganhos     = df[df["status"] == "won"]
        perdidos   = df[df["status"] == "lost"]
        abertos    = df[df["status"] == "open"]
        taxa_ganho = len(ganhos) / total * 100 if total else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: kpi_card("Total Deals", f"{total:,}".replace(",", "."))
        with c2: kpi_card("Em Aberto",   f"{len(abertos):,}".replace(",", "."))
        with c3: kpi_card("Ganhos",      f"{len(ganhos):,}".replace(",", "."), variant="success")
        with c4: kpi_card("Perdidos",    f"{len(perdidos):,}".replace(",", "."), variant="danger")
        with c5:
            kpi_card("Taxa Ganho", f"{taxa_ganho:.1f}%",
                     variant="success" if taxa_ganho > 30 else "warning")

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: kpi_card("Pipeline Aberto", fmt_brl(abertos["value"].sum()))
        with c2: kpi_card("Valor Ganho", fmt_brl(ganhos["value"].sum()), variant="success")

        # ── Eficiência & Previsão (06/06) ────────────────────────────────
        # Win rate REAL = ganhos / (ganhos + perdidos) — só negócios FECHADOS.
        # (A "Taxa Ganho" acima inclui abertos no denominador, subestima a eficiência.)
        fechados = len(ganhos) + len(perdidos)
        win_rate = len(ganhos) / fechados * 100 if fechados else 0
        # Velocidade: dias médios entre criação e ganho — query dedicada
        try:
            _union_vel = "\n  UNION ALL\n".join([
                f"SELECT add_time, won_time, value, status FROM `{tbl}` WHERE is_deleted IS NOT TRUE"
                for tbl in PIPELINES.values()
            ])
            df_vel = query(f"""
                WITH d AS ({_union_vel})
                SELECT
                  ROUND(AVG(DATE_DIFF(DATE(won_time), DATE(add_time), DAY)), 0) AS dias_medio_ganho
                FROM d
                WHERE status = 'won' AND won_time IS NOT NULL AND add_time IS NOT NULL
                  AND DATE_DIFF(DATE(won_time), DATE(add_time), DAY) BETWEEN 0 AND 365
            """)
            ciclo = int(df_vel["dias_medio_ganho"].iloc[0]) if not df_vel.empty and pd.notna(df_vel["dias_medio_ganho"].iloc[0]) else 0
        except Exception:
            ciclo = 0
        # Forecast ponderado: pipeline aberto × win rate histórico (modelo explicável)
        forecast_crm = float(abertos["value"].sum()) * (win_rate / 100)

        st.markdown("<br>", unsafe_allow_html=True)
        e1, e2, e3 = st.columns(3)
        with e1:
            kpi_card("Win Rate (fechados)", f"{win_rate:.1f}%",
                     variant="success" if win_rate >= 40 else "warning")
        with e2:
            kpi_card("Ciclo Médio de Venda", f"{ciclo} dias" if ciclo else "—")
        with e3:
            kpi_card("Forecast Ponderado", fmt_brl(forecast_crm), variant="success")
        st.caption("Forecast = Pipeline Aberto × Win Rate histórico (modelo simples e explicável). "
                   "Win Rate = ganhos ÷ (ganhos + perdidos), só negócios fechados. "
                   "Ciclo = dias médios entre criação e ganho do deal.")

        st.markdown("<br>", unsafe_allow_html=True)
        col_stage, col_owner = st.columns(2)

        with col_stage:
            stage_data = (df[df["status"] == "open"]
                          .groupby(["stage_order", "stage_name"], dropna=False)
                          .agg(deals=("deal_id", "count"), valor=("value", "sum"))
                          .reset_index()
                          .sort_values("stage_order"))
            if not stage_data.empty:
                fig = px.bar(stage_data, x="deals", y="stage_name", orientation="h",
                             title="Deals em Aberto por Estágio",
                             labels={"deals": "Deals", "stage_name": ""},
                             color_discrete_sequence=["#1E1882"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)

        with col_owner:
            owner_data = (df.groupby(df["owner_nome"].fillna("Sem owner"))
                          .agg(deals=("deal_id", "count"), pipeline=("value", "sum"))
                          .reset_index().rename(columns={"owner_nome": "Vendedor"}))
            owner_data = owner_data.sort_values("pipeline", ascending=False).head(10)
            if not owner_data.empty:
                fig2 = px.bar(owner_data, x="pipeline", y="Vendedor", orientation="h",
                              title="Pipeline (R$) por Vendedor — Top 10",
                              labels={"pipeline": "R$", "Vendedor": ""},
                              color_discrete_sequence=["#0D8B92"])
                fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig2, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Deals em aberto — Top 30 por valor**")
        df_abertos = abertos[["pipeline_nome", "title", "stage_name", "owner_nome", "value"]].copy()
        df_abertos = df_abertos.sort_values("value", ascending=False).head(30)
        df_abertos["value"] = df_abertos["value"].apply(fmt_brl)
        df_abertos.columns = ["Pipeline", "Deal", "Estágio", "Vendedor", "Valor"]
        st.dataframe(df_abertos, use_container_width=True, hide_index=True)

# ── Ranking Clientes ─────────────────────────────────────────
with tab_clientes:
    section_title("Ranking de Clientes por Faturamento")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.RANKING_CLIENTES}` ORDER BY faturamento DESC LIMIT 100",
        bronze_sql=f"""
            -- Mesma metodologia da Matriz RFV / Vendas (senão o mesmo cliente dá número
            -- diferente entre abas): invoice_date + product_amount + filtros canônicos
            -- (venda faturada, natureza financeira, sem e-commerce), janela = a do RFV
            -- (12 meses até o último mês fechado). Agrupa por NOME normalizado pra não
            -- rachar empresa com vários endereços (AIR LIQUIDE em 13 cidades).
            WITH base AS (
                SELECT
                  UPPER(TRIM(p.partner_name)) AS nome_norm,
                  p.partner_name, p.city, p.state,
                  o.order_number, o.product_amount
                FROM `{ORDERS}.fact_sales_order` o
                JOIN `{PROJ}.dm_partners.dim_partner` p USING (partner_code)
                JOIN `{ORDERS}.dim_operation_nature` n
                  ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
                WHERE o.order_status IN (3, 4)
                  AND o.channel_code <> '000054'
                  AND o.invoice_date BETWEEN
                      DATE_TRUNC(DATE_SUB((SELECT MAX(DATE(data_referencia))
                          FROM `{PROJ}.silver_comercial.silver_com_rfv_score`), INTERVAL 1 YEAR), MONTH)
                      AND (SELECT MAX(DATE(data_referencia))
                          FROM `{PROJ}.silver_comercial.silver_com_rfv_score`)
            )
            SELECT
              ANY_VALUE(partner_name) AS cliente,
              ARRAY_AGG(city  IGNORE NULLS ORDER BY product_amount DESC LIMIT 1)[SAFE_OFFSET(0)] AS city,
              ARRAY_AGG(state IGNORE NULLS ORDER BY product_amount DESC LIMIT 1)[SAFE_OFFSET(0)] AS state,
              COUNT(DISTINCT order_number) AS qtd_pedidos,
              SUM(product_amount)   AS faturamento
            FROM base
            GROUP BY nome_norm
            ORDER BY faturamento DESC
            LIMIT 100
        """,
        label="Ranking Clientes",
    )

    if not df.empty:
        val_col  = next((c for c in ["faturamento", "valor_total"] if c in df.columns), None)
        nome_col = next((c for c in ["cliente", "partner_name", "nome"] if c in df.columns), None)

        # ── Análise ABC / Pareto (concentração de receita) — visão de RISCO ──
        if val_col:
            df_abc = df.copy()
            df_abc[val_col] = pd.to_numeric(df_abc[val_col], errors="coerce").fillna(0)
            df_abc = df_abc.sort_values(val_col, ascending=False).reset_index(drop=True)
            total_fat = df_abc[val_col].sum()
            df_abc["acum_pct"] = df_abc[val_col].cumsum() / total_fat * 100
            df_abc["rank_pct"] = (df_abc.index + 1) / len(df_abc) * 100
            # Classe ABC: A = até 80% acum, B = 80-95%, C = resto
            def _classe(p):
                return "A" if p <= 80 else ("B" if p <= 95 else "C")
            df_abc["classe"] = df_abc["acum_pct"].apply(_classe)
            n_a = (df_abc["classe"] == "A").sum()
            fat_top20 = df_abc.head(max(1, int(len(df_abc) * 0.2)))[val_col].sum()
            pct_top20 = fat_top20 / total_fat * 100 if total_fat else 0

            k1, k2, k3 = st.columns(3)
            with k1: kpi_card("Top 100 Faturamento", fmt_brl(total_fat))
            with k2:
                kpi_card("Classe A (80% receita)", f"{n_a} clientes",
                         variant="warning" if n_a <= 10 else "success")
            with k3:
                kpi_card("Concentração Top 20%", f"{pct_top20:.0f}%",
                         variant="danger" if pct_top20 >= 80 else "warning")
            st.caption("Curva ABC: Classe A = clientes que somam 80% do faturamento. "
                       "Concentração alta no Top 20% = risco estratégico (dependência de poucos clientes).")

            st.markdown("<br>", unsafe_allow_html=True)
            colp1, colp2 = st.columns([3, 2])
            with colp1:
                if nome_col:
                    fig = px.bar(df_abc.head(15), x=val_col, y=nome_col, orientation="h",
                                 title="Top 15 Clientes", labels={val_col: "R$", nome_col: ""},
                                 color="classe",
                                 color_discrete_map={"A": "#0D5C4A", "B": "#4C9A5A", "C": "#A3D977"})
                    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                      yaxis=dict(autorange="reversed"), height=520,
                                      margin=dict(l=8, r=8, t=44, b=8), legend_title_text="Classe")
                    st.plotly_chart(fig, use_container_width=True)
            with colp2:
                # Curva de Pareto
                fig_par = go.Figure()
                fig_par.add_trace(go.Scatter(x=df_abc["rank_pct"], y=df_abc["acum_pct"],
                                             mode="lines", line=dict(color="#1E1882", width=3),
                                             name="Receita acumulada"))
                fig_par.add_hline(y=80, line_dash="dot", line_color="#DC2626",
                                  annotation_text="80% receita")
                fig_par.update_layout(title="Curva de Pareto (concentração)",
                                      xaxis_title="% dos clientes", yaxis_title="% receita acum.",
                                      plot_bgcolor="white", paper_bgcolor="white",
                                      margin=dict(t=44), height=520)
                st.plotly_chart(fig_par, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Detalhamento — Top 100**")

        # Formata tabela de forma legível
        df_show = df.copy()
        if val_col:
            df_show[val_col] = df_show[val_col].apply(lambda v: fmt_brl(float(v)) if pd.notna(v) else "—")
        if "qtd_pedidos" in df_show.columns:
            df_show["qtd_pedidos"] = df_show["qtd_pedidos"].fillna(0).astype(int)
        # Renomeia colunas pra apresentação
        ren = {
            "cliente": "Cliente",
            "partner_name": "Cliente",
            "city": "Cidade",
            "state": "UF",
            "qtd_pedidos": "Pedidos",
            "faturamento": "Faturamento",
            "valor_total": "Faturamento",
        }
        df_show = df_show.rename(columns={k: v for k, v in ren.items() if k in df_show.columns})
        st.dataframe(df_show, use_container_width=True, hide_index=True)

# RFV Matrix
with tab_rfv:
    section_title("Matriz RFV — Recência × Frequência × Valor")

    SILVER_COM = f"{PROJ}.silver_comercial"
    GOLD_COM   = f"{PROJ}.gold_comercial"

    SEG_MAP = {
        ("F1", "R1"): (1, "Campeões"),
        ("F1", "R2"): (2, "Fiéis"), ("F1", "R3"): (2, "Fiéis"),
        ("F1", "R4"): (8, "Não pode\nperder"), ("F1", "R5"): (8, "Não pode\nperder"),
        ("F2", "R1"): (2, "Fiéis"), ("F2", "R2"): (2, "Fiéis"),
        ("F2", "R3"): (2, "Fiéis"),
        ("F2", "R4"): (9, "Em risco"), ("F2", "R5"): (9, "Em risco"),
        ("F3", "R1"): (3, "Fiéis em\nPotencial"), ("F3", "R2"): (3, "Fiéis em\nPotencial"),
        ("F3", "R3"): (6, "Precisando\nde Atenção"),
        ("F3", "R4"): (9, "Em risco"), ("F3", "R5"): (9, "Em risco"),
        ("F4", "R1"): (3, "Fiéis em\nPotencial"), ("F4", "R2"): (3, "Fiéis em\nPotencial"),
        ("F4", "R3"): (7, "Quase\nDormentes"),
        ("F4", "R4"): (10, "Hibernando"), ("F4", "R5"): (11, "Perdidos"),
        ("F5", "R1"): (4, "Novos\nClientes"), ("F5", "R2"): (5, "Promessas"),
        ("F5", "R3"): (7, "Quase\nDormentes"),
        ("F5", "R4"): (11, "Perdidos"), ("F5", "R5"): (11, "Perdidos"),
    }

    CELL_BG = {
        0: "#EAECF0",
        1: "#0D2B6B",
        2: "#0D8B92",
        3: "#B8CCE4",
        4: "#92D050",
        5: "#7030A0",
        6: "#FFD966",
        7: "#FFC000",
        8: "#D9E2F3",
        9: "#F4C7AB",
        10: "#95A5C1",
        11: "#C55A11",
    }
    CELL_TXT = {
        0: "#6B7280", 1: "#FFFFFF", 2: "#FFFFFF", 3: "#000000",
        4: "#000000", 5: "#000000", 6: "#000000", 7: "#000000",
        8: "#000000", 9: "#000000", 10: "#000000", 11: "#000000",
    }

    cf1, cf2, cf3 = st.columns([2, 2, 2])
    with cf1:
        familia_sel = st.selectbox(
            "Família RFV", ["TODOS", "HOSPITALAR", "FARMACIAS", "SAC"],
            key="rfv_familia",
        )

    # Período de referência — lista datas disponíveis na tabela
    # (vem antes do filtro de vendedor para que vendedores sejam escopados ao período)
    try:
        # cache-bust: 2026-05-26-v2 (após rebuild completo dos snapshots históricos)
        df_periods = query(f"""
            SELECT DISTINCT DATE(data_referencia) AS periodo
            FROM `{SILVER_COM}.silver_com_rfv_score`
            ORDER BY 1 DESC LIMIT 13
        """)
        period_list = df_periods["periodo"].tolist()
        _MES_PT = {
            1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
            7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro",
        }
        _MES_ABR = {
            1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
            7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez",
        }
        # RFV é janela móvel de 12 meses (não o mês isolado). Label mostra a janela
        # completa "Mai/2025 → Mai/2026" para quem é de fora entender (pedido Victor 02/06).
        def _label_janela(p):
            fim = pd.to_datetime(p)
            ini = fim - pd.DateOffset(years=1)
            return f"{_MES_ABR[ini.month]}/{ini.year} → {_MES_ABR[fim.month]}/{fim.year}"
        period_labels = [_label_janela(p) for p in period_list]
    except Exception:
        period_list = []
        period_labels = []

    with cf3:
        if period_list:
            periodo_idx = st.selectbox(
                "Período de referência",
                range(len(period_list)),
                format_func=lambda i: period_labels[i],
                key="rfv_periodo",
            )
            periodo_sel = str(period_list[periodo_idx])
            periodo_w = f"AND DATE(data_referencia) = '{periodo_sel}'"
            periodo_w_pre = f"AND DATE(data_referencia) = '{periodo_sel}'"
        else:
            periodo_w = ""
            periodo_w_pre = ""
            st.caption("Período: cálculo mais recente")

    # Vendedores escopados por família + período (só mostra quem realmente atua ali)
    fam_w_pre = f"AND rfv_familia = '{familia_sel}'" if familia_sel != "TODOS" else ""
    try:
        df_vendedores_opts = query(f"""
            SELECT DISTINCT {SP_DISPLAY} AS vendedor
            FROM `{SILVER_COM}.silver_com_rfv_score`
            WHERE 1=1 {fam_w_pre} {periodo_w_pre} {GIOVANNA_RESIDUO_FILTER}
            ORDER BY 1
        """)
        vendedor_options = ["TODOS"] + df_vendedores_opts["vendedor"].dropna().astype(str).tolist()
    except Exception:
        vendedor_options = ["TODOS"]

    # Reseta o vendedor selecionado se ele não pertence mais à família/período atual
    if st.session_state.get("rfv_vendedor") not in vendedor_options:
        st.session_state["rfv_vendedor"] = "TODOS"

    with cf2:
        vendedor_sel = st.selectbox(
            "Carteira",
            vendedor_options,
            key="rfv_vendedor",
        )

    fam_w = f"AND rfv_familia = '{familia_sel}'" if familia_sel != "TODOS" else ""
    # Filtro usa o nome de display (já normalizado), então funciona para "Cliente Novo",
    # "Guilherme Aquino", "Kauã Rodrigues", "Kauan Ramos" etc.
    vend_w = f"AND {SP_DISPLAY} = '{vendedor_sel}'" if vendedor_sel != "TODOS" else ""
    # Regra Alves (confirmada 05/06/2026): Eduardo Marques só entra no GERAL,
    # não no detalhamento das carteiras (Hospitalar/Farmácia/SAC). Quando o
    # filtro de família é TODOS, mantemos ele; quando é uma família específica,
    # excluímos pra alinhar 100% com a planilha.
    eduardo_w = "AND COALESCE(rfv_salesperson, '') NOT LIKE 'Eduardo%'" if familia_sel != "TODOS" else ""
    where = f"WHERE 1=1 {fam_w} {vend_w} {periodo_w} {eduardo_w} {GIOVANNA_RESIDUO_FILTER}"

    with st.spinner("Consultando BigQuery..."):
        try:
            df_kpi = query(f"""
                SELECT
                    COUNT(DISTINCT partner_name) AS total_clientes,
                    COUNTIF(classificacao_3 = 1) AS campeoes,
                    COUNTIF(classificacao_3 = 2) AS fieis,
                    COUNTIF(classificacao_3 = 3) AS fp,
                    COUNTIF(classificacao_3 = 8) AS nao_pode_perder,
                    COUNTIF(classificacao_3 = 10) AS hibernando,
                    COUNTIF(classificacao_3 IN (9, 10)) AS em_risco,
                    COUNTIF(classificacao_3 = 11) AS perdidos,
                    ROUND(SUM(valor_total), 0) AS faturamento,
                    MAX(data_referencia) AS data_referencia
                FROM `{SILVER_COM}.silver_com_rfv_score`
                {where}
            """)
            df_cells = query(f"""
                SELECT
                    freq_bucket,
                    rec_bucket,
                    classificacao_2 AS segmento,
                    classificacao_3 AS seg_num,
                    COUNT(DISTINCT partner_name) AS clientes,
                    ROUND(SUM(valor_total), 2) AS faturamento
                FROM `{SILVER_COM}.silver_com_rfv_score`
                {where}
                GROUP BY 1, 2, 3, 4
            """)
            df_segmentos = query(f"""
                SELECT
                    classificacao_3 AS seg_num,
                    ANY_VALUE(classificacao_2) AS segmento,
                    COUNT(DISTINCT partner_name) AS clientes,
                    ROUND(SUM(valor_total), 2) AS faturamento
                FROM `{SILVER_COM}.silver_com_rfv_score`
                {where}
                GROUP BY 1
                ORDER BY 1
            """)
            # Painel por vendedor — RFV vem do silver (respeita periodo_sel da matriz),
            # CRM/deals/alertas vem da gold (snapshot mais recente).
            fam_painel = f"AND rfv_familia = '{familia_sel}'" if familia_sel != "TODOS" else ""
            df_painel_rfv = query(f"""
                SELECT
                    {SP_DISPLAY} AS rfv_salesperson,
                    COUNT(DISTINCT partner_name) AS qtd_clientes_carteira,
                    COUNTIF(classificacao_1 = 'F1R1') AS qtd_campeoes,
                    COUNTIF(classificacao_1 IN ('F1R2','F1R3','F2R1','F2R2','F2R3')) AS qtd_fieis,
                    COUNTIF(classificacao_1 IN ('F3R1','F3R2','F4R1','F4R2')) AS qtd_fieis_potencial,
                    COUNTIF(classificacao_1 IN ('F5R1','F5R2')) AS qtd_novos_promessas,
                    COUNTIF(classificacao_1 = 'F3R3') AS qtd_precisando_atencao,
                    COUNTIF(classificacao_1 IN ('F1R4','F1R5')) AS qtd_nao_pode_perder,
                    COUNTIF(classificacao_1 IN ('F4R3','F5R3')) AS qtd_quase_dormentes,
                    COUNTIF(classificacao_1 IN ('F2R4','F2R5','F3R4','F3R5','F4R4')) AS qtd_em_risco_hibernando,
                    COUNTIF(classificacao_1 IN ('F4R5','F5R4','F5R5')) AS qtd_perdidos,
                    ROUND(SUM(valor_total), 0) AS faturamento,
                    ROUND(SAFE_DIVIDE(SUM(valor_total), NULLIF(COUNT(DISTINCT partner_name), 0)), 0) AS ticket_medio
                FROM `{SILVER_COM}.silver_com_rfv_score`
                WHERE COALESCE(rfv_salesperson, 'Cliente Novo') NOT LIKE 'Eduardo%'
                  AND COALESCE(rfv_salesperson, 'Cliente Novo') NOT LIKE 'Karina%'
                  {fam_painel} {periodo_w} {GIOVANNA_RESIDUO_FILTER}
                GROUP BY 1
                ORDER BY faturamento DESC
            """)
            # CRM/alertas — sempre da foto mais recente da gold (não tem histórico mensal)
            df_painel_crm = query(f"""
                SELECT
                    {SP_DISPLAY} AS rfv_salesperson,
                    SUM(qtd_clientes_carteira) AS qtd_clientes_ativos,
                    SUM(crm_deals_open) AS crm_deals_open,
                    ROUND(SUM(crm_valor_pipeline), 0) AS pipeline_crm,
                    SUM(alertas_oportunidade) AS alertas_oportunidade,
                    SUM(alertas_churn) AS alertas_churn,
                    SUM(clientes_fora_radar) AS clientes_fora_radar
                FROM `{GOLD_COM}.gold_com_vendedor_painel`
                WHERE rfv_salesperson NOT LIKE 'Eduardo%'
                  AND rfv_salesperson NOT LIKE 'Karina%'
                  {fam_painel}
                  AND DATE(data_referencia) = (SELECT MAX(DATE(data_referencia)) FROM `{GOLD_COM}.gold_com_vendedor_painel`)
                GROUP BY 1
            """)
            df_painel = df_painel_rfv.merge(df_painel_crm, on='rfv_salesperson', how='left')
            for col in ['crm_deals_open','pipeline_crm','alertas_oportunidade','alertas_churn','clientes_fora_radar']:
                if col in df_painel.columns:
                    df_painel[col] = df_painel[col].fillna(0).astype(int)
            # Coluna "Clientes" = tamanho da CARTEIRA ATIVA (gold, por nome). Para "Novos
            # Clientes" (não-carteirizados) não há carteira ativa, então cai no nº de
            # clientes que compraram no período (silver). Mantém alertas e clientes na
            # mesma base (carteira) e evita "73 clientes / 151 fora do radar".
            if 'qtd_clientes_ativos' in df_painel.columns:
                df_painel['qtd_clientes_carteira'] = (
                    df_painel['qtd_clientes_ativos']
                    .fillna(df_painel['qtd_clientes_carteira'])
                    .astype(int)
                )
                # Recalcula o ticket sobre a MESMA base da coluna Clientes (carteira ativa),
                # senão Fat ÷ Clientes não fecha com o Ticket exibido. Vira "faturamento
                # por cliente da carteira" — auditável na tela.
                df_painel['ticket_medio'] = (
                    df_painel['faturamento']
                    / df_painel['qtd_clientes_carteira'].replace(0, pd.NA)
                ).round(0).fillna(0)
            # Alertas — tabela com 3 dimensoes de duplicacao (filiais, familias, snapshots).
            # Estrategia: dedup por NOME da empresa + tipo_alerta. Cada empresa conta 1x por alerta,
            # mesmo que tenha varias filiais (partner_code) e/ou apareca em multiplas familias.
            fam_alerta = f"AND rfv_familia = '{familia_sel}'" if familia_sel != "TODOS" else ""
            df_alertas = query(f"""
                WITH dedup AS (
                    SELECT
                        UPPER(TRIM(partner_name)) AS nome_norm,
                        tipo_alerta,
                        MAX(faturamento_periodo) AS faturamento_periodo
                    FROM `{GOLD_COM}.gold_com_alerta_comercial`
                    WHERE rfv_salesperson NOT LIKE 'Eduardo%'
                      AND rfv_salesperson NOT LIKE 'Karina%'
                      {fam_alerta}
                    GROUP BY 1, 2
                )
                SELECT
                    tipo_alerta,
                    COUNT(DISTINCT nome_norm) AS qtd,
                    ROUND(SUM(faturamento_periodo), 0) AS valor_total
                FROM dedup
                GROUP BY tipo_alerta
                ORDER BY qtd DESC
            """)
            data_ok = True
        except Exception as e:
            st.error(f"Erro ao consultar BigQuery: {e}")
            data_ok = False

    if not data_ok:
        st.stop()

    def _fmt_fat(v: float) -> str:
        if v >= 1000000:
            return f"R$ {v / 1000000:.1f}M"
        if v >= 1000:
            return f"R$ {v / 1000:.0f}k"
        return f"R$ {v:,.0f}"

    if not df_kpi.empty:
        row = df_kpi.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Total Clientes", f'{int(row["total_clientes"]):,}')
        with c2:
            kpi_card("Campeões", f'{int(row["campeoes"]):,}', variant="success")
        with c3:
            kpi_card("Fiéis", f'{int(row["fieis"]):,}', variant="success")
        with c4:
            kpi_card("Fiéis em Potencial", f'{int(row["fp"]):,}', variant="success")

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            kpi_card("Não Pode Perder", f'{int(row["nao_pode_perder"]):,}', variant="warning")
        with c6:
            kpi_card("Em Risco + Hibernando", f'{int(row["em_risco"]):,}', variant="warning")
        with c7:
            kpi_card("Perdidos", f'{int(row["perdidos"]):,}', variant="danger")
        with c8:
            kpi_card("Faturamento", fmt_brl(float(row["faturamento"])))

        data_ref = pd.to_datetime(row["data_referencia"]).strftime("%d/%m/%Y")
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 100%);
                border: 1px solid #E5E7EB;
                border-left: 4px solid #1E1882;
                border-radius: 12px;
                padding: 14px 16px;
                margin-top: 12px;
            ">
                <div style="font-size:13px;font-weight:700;color:#111827;">Leitura operacional da matriz</div>
                <div style="font-size:12px;color:#4B5563;margin-top:4px;">
                    Base dinâmica atualizada em <b>{data_ref}</b>. A recência é móvel e acompanha a última janela disponível do Data Lake,
                    então os totais podem variar diariamente conforme novas compras entram na base.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    f_thresh = {
        "HOSPITALAR": [("F1", "5x ou mais"), ("F2", "4x"), ("F3", "3x"), ("F4", "2x"), ("F5", "1x")],
        "SAC": [("F1", "5x ou mais"), ("F2", "4x"), ("F3", "3x"), ("F4", "2x"), ("F5", "1x")],
        "FARMACIAS": [("F1", "7x ou mais"), ("F2", "5-6x"), ("F3", "3-4x"), ("F4", "2x"), ("F5", "1x")],
        "TODOS": [("F1", ""), ("F2", ""), ("F3", ""), ("F4", ""), ("F5", "")],
    }
    f_labels = f_thresh.get(familia_sel, f_thresh["TODOS"])
    r_labels = [
        ("R1", "Últimos 30 dias"),
        ("R2", "31 a 60 dias"),
        ("R3", "61 a 120 dias"),
        ("R4", "121 a 180 dias"),
        ("R5", "181 a 360 dias"),
    ]

    cell_data = {}
    if not df_cells.empty:
        for _, r in df_cells.iterrows():
            cell_data[(r["freq_bucket"], r["rec_bucket"])] = {
                "clientes": int(r["clientes"]),
                "faturamento": float(r["faturamento"]),
                "seg_num": int(r["seg_num"]),
                "segmento": str(r["segmento"]),
            }

    def _fmt_brl_board(v: float) -> str:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    segment_lookup = {
        int(r["seg_num"]): {
            "segmento": str(r["segmento"]),
            "clientes": int(r["clientes"]),
            "faturamento": float(r["faturamento"]),
        }
        for _, r in df_segmentos.iterrows()
    } if not df_segmentos.empty else {}

    segment_display = {
        1: {"nome": "Campeões", "area": "3 / 3 / 5 / 4", "bg": "#0D2B6B", "fg": "#FFFFFF"},
        2: {"nome": "Fiéis", "area": "3 / 4 / 5 / 6", "bg": "#0D8B92", "fg": "#FFFFFF"},
        3: {"nome": "Fiéis em potencial", "area": "5 / 3 / 7 / 5", "bg": "#B8CCE4", "fg": "#000000"},
        4: {"nome": "Novos clientes", "area": "7 / 3 / 8 / 4", "bg": "#92D050", "fg": "#000000"},
        5: {"nome": "Promessas", "area": "7 / 4 / 8 / 5", "bg": "#7030A0", "fg": "#000000"},
        6: {"nome": "Precisando de atenção", "area": "5 / 5 / 6 / 6", "bg": "#FFD966", "fg": "#000000"},
        7: {"nome": "Quase dormentes", "area": "6 / 5 / 8 / 6", "bg": "#FFC000", "fg": "#000000"},
        8: {"nome": "Não pode perder", "area": "3 / 6 / 4 / 8", "bg": "#D9E2F3", "fg": "#000000"},
        9: {"nome": "Em risco", "area": "4 / 6 / 6 / 8", "bg": "#F4C7AB", "fg": "#000000"},
        10: {"nome": "Hibernando", "area": "6 / 6 / 7 / 7", "bg": "#95A5C1", "fg": "#000000"},
        11: {"nome": "Perdidos", "area": "7 / 6 / 8 / 8", "bg": "#C55A11", "fg": "#000000"},
    }

    # Perdidos "satelite" (F4 R5) — mesma cor, sem numero, para visualmente ocupar a celula superior direita
    perdidos_satelite_area = "6 / 7 / 7 / 8"

    freq_desc_display = {
        "HOSPITALAR": {"F1": "5 vezes ou mais", "F2": "Entre 4", "F3": "Entre 3", "F4": "Entre 2", "F5": "1 vez"},
        "SAC": {"F1": "5 vezes ou mais", "F2": "Entre 4", "F3": "Entre 3", "F4": "Entre 2", "F5": "1 vez"},
        "FARMACIAS": {"F1": "7 vezes ou mais", "F2": "Entre 5 e 6", "F3": "Entre 3 e 4", "F4": "Entre 2", "F5": "1 vez"},
    }
    freq_desc_selected = freq_desc_display.get(
        familia_sel,
        {bucket: (desc or "") for bucket, desc in f_labels},
    )
    left_rows = {
        "F1": {"desc": freq_desc_selected.get("F1", ""), "code_bg": "#375623", "desc_bg": "#375623", "row": 3},
        "F2": {"desc": freq_desc_selected.get("F2", ""), "code_bg": "#5E8E3E", "desc_bg": "#5E8E3E", "row": 4},
        "F3": {"desc": freq_desc_selected.get("F3", ""), "code_bg": "#A9D18E", "desc_bg": "#A9D18E", "row": 5},
        "F4": {"desc": freq_desc_selected.get("F4", ""), "code_bg": "#C6E0B4", "desc_bg": "#C6E0B4", "row": 6},
        "F5": {"desc": freq_desc_selected.get("F5", ""), "code_bg": "#E2F0D9", "desc_bg": "#E2F0D9", "row": 7},
    }

    rec_headers = [
        ("R1", "Últimos 30 dias", "#375623", "#375623"),
        ("R2", "R2", "#5E8E3E", "#5E8E3E"),
        ("R3", "R3", "#A9D18E", "#A9D18E"),
        ("R4", "R4", "#C6E0B4", "#C6E0B4"),
        ("R5", "R5", "#E2F0D9", "#E2F0D9"),
    ]
    rec_descs = [
        ("R1", "Últimos 30 dias", "#375623"),
        ("R2", "Entre 31 e 60 dias", "#5E8E3E"),
        ("R3", "Entre 61 e 120 dias", "#A9D18E"),
        ("R4", "Entre 121 e 180 dias", "#C6E0B4"),
        ("R5", "Entre 181 e 360 dias", "#E2F0D9"),
    ]

    matrix_css = """
    <style>
    .rfv-excel-wrap {
        overflow-x: auto;
        margin-bottom: 8px;
        padding-bottom: 4px;
    }
    .rfv-excel {
        min-width: 1180px;
        display: grid;
        grid-template-columns: 76px 134px 1.25fr 1fr 1.18fr 1.18fr 1.18fr;
        grid-template-rows: 56px 72px 94px 30px 98px 72px 102px;
        gap: 1px;
        background: #1F1F1F;
        border: 1px solid #1F1F1F;
    }
    .rfv-excel > div {
        background: #FFFFFF;
        box-sizing: border-box;
    }
    .rfv-top-label {
        background: #C00000 !important;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-size: 16px;
        font-weight: 700;
        padding: 6px 12px;
    }
    .rfv-rec-code,
    .rfv-rec-desc,
    .rfv-freq-code,
    .rfv-freq-desc {
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 4px 8px;
        color: #000000;
    }
    .rfv-rec-code { font-size: 18px; font-weight: 700; }
    .rfv-rec-desc { font-size: 14px; font-weight: 500; }
    .rfv-freq-code { font-size: 18px; font-weight: 700; }
    .rfv-freq-desc { font-size: 14px; font-weight: 500; }
    .rfv-seg-card {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        text-align: center;
        padding: 10px 14px 14px;
    }
    .rfv-seg-title {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.15;
        margin-top: 2px;
    }
    .rfv-seg-count {
        font-size: 22px;
        font-weight: 800;
        line-height: 1;
        margin-top: 10px;
    }
    .rfv-seg-money {
        width: 100%;
        margin-top: auto;
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
        font-size: 16px;
        font-weight: 700;
        line-height: 1;
    }
    .rfv-seg-money span:first-child {
        min-width: 30px;
        text-align: left;
    }
    .rfv-seg-money span:last-child {
        flex: 1;
        text-align: right;
    }
    </style>
    """

    def _segment_block(seg_num: int) -> str:
        cfg = segment_display[seg_num]
        seg = segment_lookup.get(seg_num, {})
        clientes = int(seg.get("clientes", 0))
        faturamento = float(seg.get("faturamento", 0.0))
        return (
            f'<div class="rfv-seg-card" style="grid-area:{cfg["area"]};background:{cfg["bg"]};color:{cfg["fg"]};">'
            f'<div class="rfv-seg-title">{cfg["nome"]}</div>'
            f'<div class="rfv-seg-count">{clientes}</div>'
            f'<div class="rfv-seg-money"><span>R$</span><span>{_fmt_brl_board(faturamento)}</span></div>'
            f'</div>'
        )

    headers_html = ""
    for idx, (code, _, bg_code, _) in enumerate(rec_headers, start=3):
        headers_html += (
            f'<div class="rfv-rec-code" style="grid-area:1 / {idx} / 2 / {idx + 1};background:{bg_code};">'
            f'{code}</div>'
        )
    for idx, (_, desc, bg) in enumerate(rec_descs, start=3):
        headers_html += (
            f'<div class="rfv-rec-desc" style="grid-area:2 / {idx} / 3 / {idx + 1};background:{bg};">'
            f'{desc}</div>'
        )

    left_html = ""
    for code, cfg in left_rows.items():
        row = cfg["row"]
        left_html += (
            f'<div class="rfv-freq-code" style="grid-area:{row} / 1 / {row + 1} / 2;background:{cfg["code_bg"]};">'
            f'{code}</div>'
            f'<div class="rfv-freq-desc" style="grid-area:{row} / 2 / {row + 1} / 3;background:{cfg["desc_bg"]};">'
            f'{cfg["desc"]}</div>'
        )

    # Bloco satelite Perdidos (F4 R5) — visualmente preenche a celula sem repetir numero
    perdidos_bg = segment_display[11]["bg"]
    perdidos_satelite = (
        f'<div class="rfv-seg-card" '
        f'style="grid-area:{perdidos_satelite_area};background:{perdidos_bg};"></div>'
    )
    # Renderiza Perdidos satelite ANTES do Hibernando para nao sobrepor
    seg_html = perdidos_satelite + "".join(_segment_block(seg_num) for seg_num in [1, 2, 8, 9, 3, 6, 11, 10, 4, 5, 7])

    matrix_html = f"""
    {matrix_css}
    <div class="rfv-excel-wrap">
      <div class="rfv-excel">
        <div class="rfv-top-label" style="grid-area:1 / 1 / 2 / 3;">Data última compra</div>
        <div class="rfv-top-label" style="grid-area:2 / 1 / 3 / 3;">Frequência em 12 meses</div>
        {headers_html}
        {left_html}
        {seg_html}
      </div>
    </div>
    """
    st.markdown(matrix_html, unsafe_allow_html=True)

    GLOSSARIO = [
        (1, "", "Campeões", CELL_BG[1], CELL_TXT[1], "F1 + R1. Compraram na maior frequência da família e tiveram a última compra nos últimos 30 dias."),
        (2, "", "Fiéis", CELL_BG[2], CELL_TXT[2], "F1/F2 com recência entre 0 e 120 dias. Mantêm alta recorrência e já têm hábito de compra consistente."),
        (3, "", "Fiéis em Potencial", CELL_BG[3], CELL_TXT[3], "F3/F4 em R1-R2. Compraram nos últimos 60 dias e estão próximos de virar Fiéis — manter contato para acelerar a segunda compra."),
        (4, "", "Novos Clientes", CELL_BG[4], CELL_TXT[4], "F5 + R1. Fizeram 1 compra nos últimos 30 dias."),
        (5, "", "Promessas", CELL_BG[5], CELL_TXT[5], "F5 + R2. Fizeram 1 compra há 31 a 60 dias e ainda não recompraram."),
        (6, "", "Precisando de Atenção", CELL_BG[6], CELL_TXT[6], "F3 + R3. Estão entre 61 e 120 dias sem comprar e precisam de ação antes de migrar para risco."),
        (7, "", "Quase Dormentes", CELL_BG[7], CELL_TXT[7], "F4/F5 + R3. Baixa recorrência e última compra entre 61 e 120 dias."),
        (8, "", "Não Pode Perder", CELL_BG[8], CELL_TXT[8], "F1 + R4/R5. Eram muito recorrentes, mas estão entre 121 e 360 dias sem comprar."),
        (9, "", "Em Risco", CELL_BG[9], CELL_TXT[9], "F2/F3 + R4/R5. Já estão há 121 a 360 dias sem compra e precisam de retomada urgente."),
        (10, "", "Hibernando", CELL_BG[10], CELL_TXT[10], "F4 + R4. Baixa frequência e última compra há 121 a 180 dias."),
        (11, "", "Perdidos", CELL_BG[11], CELL_TXT[11], "F4/F5 em R5, ou F5 em R4. Mais de 180 dias sem compra."),
    ]

    with st.expander("Glossário dos Segmentos RFV", expanded=False):
        regra_freq = {
            "HOSPITALAR": "Hospitalar/SAC: F1 = 5x ou mais, F2 = 4x, F3 = 3x, F4 = 2x, F5 = 1x.",
            "SAC": "Hospitalar/SAC: F1 = 5x ou mais, F2 = 4x, F3 = 3x, F4 = 2x, F5 = 1x.",
            "FARMACIAS": "Farmácias: F1 = 7x ou mais, F2 = 5-6x, F3 = 3-4x, F4 = 2x, F5 = 1x.",
            "TODOS": "As faixas de frequência variam por família. Use o filtro acima para ver a régua específica.",
        }
        st.markdown(
            f"""
            <div style="
                background:#F8FAFC;
                border:1px solid #E5E7EB;
                border-radius:10px;
                padding:12px 14px;
                margin-bottom:10px;
                color:#475569;
                font-size:12px;
            ">
                <b>Padronização da leitura:</b> todas as definições abaixo já trazem a lógica temporal da recência.
                {regra_freq.get(familia_sel, regra_freq["TODOS"])}
            </div>
            """,
            unsafe_allow_html=True,
        )
        g_cols = st.columns(2)
        for i, (_, icon, nome, bg, _, desc) in enumerate(GLOSSARIO):
            with g_cols[i % 2]:
                icon_html = f'<span style="font-size:20px;line-height:1;">{icon}</span>' if icon else ''
                st.markdown(
                    f'<div style="display:flex;gap:10px;align-items:flex-start;'
                    f'background:#F9FAFB;border-radius:8px;padding:10px 12px;margin-bottom:8px;'
                    f'border-left:4px solid {bg};">'
                    f'{icon_html}'
                    f'<div>'
                    f'<div style="font-weight:700;font-size:13px;color:#111;">{nome}</div>'
                    f'<div style="font-size:12px;color:#4B5563;margin-top:3px;">{desc}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    # ── Detalhe por Segmento ──────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_title("Detalhe por Segmento")
    st.caption("Lista completa dos clientes de cada segmento — equivalente à aba 'Com Formula' da planilha original.")

    _SEG_OPTIONS = {
        1:  "Campeões",
        2:  "Fiéis",
        3:  "Fiéis em Potencial",
        4:  "Novos Clientes",
        5:  "Promessas",
        6:  "Precisando de Atenção",
        7:  "Quase Dormentes",
        8:  "Não Pode Perder",
        9:  "Em Risco",
        10: "Hibernando",
        11: "Perdidos",
    }
    _SEG_VARIANT = {
        1:"success", 2:"success", 3:"success", 4:"success", 5:"success",
        6:"warning", 7:"warning", 8:"warning", 9:"warning",
        10:"danger", 11:"danger",
    }
    _SEG_META = {seg_num: {"icon": icon, "nome": nome, "bg": bg, "desc": desc} for seg_num, icon, nome, bg, _, desc in GLOSSARIO}

    _det_col1, _det_col2 = st.columns([3, 5])
    with _det_col1:
        seg_detalhe = st.selectbox(
            "Segmento",
            options=list(_SEG_OPTIONS.keys()),
            format_func=lambda k: _SEG_OPTIONS[k],
            key="rfv_seg_detalhe",
        )
    with _det_col2:
        _meta = _SEG_META[seg_detalhe]
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
                border: 1px solid #E5E7EB;
                border-left: 6px solid {_meta["bg"]};
                border-radius: 12px;
                padding: 14px 16px;
                min-height: 92px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size:14px;font-weight:800;color:#111827;">
                    {_meta["nome"]}
                </div>
                <div style="font-size:12px;color:#4B5563;margin-top:6px;line-height:1.45;">
                    {_meta["desc"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.spinner("Carregando clientes do segmento..."):
        try:
            df_det = query(f"""
                SELECT
                    partner_name                                   AS nome_cliente,
                    rfv_familia                                    AS familia,
                    {SP_DISPLAY}                                   AS vendedor,
                    FORMAT_DATE('%d/%m/%Y', ultima_compra_data)    AS ultima_compra,
                    recencia_dias                                  AS dias_sem_comprar,
                    frequencia                                     AS frequencia,
                    ROUND(valor_total, 2)                          AS valor_total
                FROM `{SILVER_COM}.silver_com_rfv_score`
                WHERE classificacao_3 = {seg_detalhe}
                {fam_w} {vend_w} {periodo_w} {GIOVANNA_RESIDUO_FILTER}
                ORDER BY valor_total DESC
            """)
            _cnt = len(df_det)
            _fat = float(df_det["valor_total"].sum()) if not df_det.empty else 0.0
            _kc1, _kc2, _kc3 = st.columns(3)
            with _kc1:
                kpi_card(
                    _SEG_OPTIONS[seg_detalhe],
                    f"{_cnt} cliente{'s' if _cnt != 1 else ''}",
                    variant=_SEG_VARIANT[seg_detalhe],
                )
            with _kc2:
                kpi_card("Faturamento do Segmento", fmt_brl(_fat))
            with _kc3:
                _tick = _fat / _cnt if _cnt else 0
                kpi_card("Ticket Médio no Segmento", fmt_brl(_tick))

            if not df_det.empty:
                df_det = df_det.rename(
                    columns={
                        "nome_cliente": "Nome do Cliente",
                        "familia": "Família",
                        "vendedor": "Carteira",
                        "ultima_compra": "Última Compra",
                        "dias_sem_comprar": "Dias sem Comprar",
                        "frequencia": "Frequência",
                        "valor_total": "Valor Total (R$)",
                    }
                )
                st.dataframe(
                    df_det,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Dias sem Comprar": st.column_config.NumberColumn(format="%d dias"),
                        "Frequência":       st.column_config.NumberColumn(format="%d pedidos"),
                    },
                )
            else:
                st.info("Nenhum cliente neste segmento com os filtros selecionados.")
        except Exception as _e_det:
            st.error(f"Erro ao carregar detalhe do segmento: {_e_det}")

    st.markdown("<br>", unsafe_allow_html=True)

    section_title("Painel por Carteira")
    _label_periodo = period_labels[periodo_idx] if period_list else "período mais recente"
    st.caption(f"Composição por carteira — segmentos RFV e faturamento da janela de **{_label_periodo}** (acompanha o filtro acima). Indicadores de CRM (deals, pipeline, alertas) usam sempre o estado atual.")

    # Nomenclatura de carteira (Hospitalar = A/B/C/D, Farmácias/SAC = nome único)
    # é resolvida no SP_DISPLAY (fonte única, aplicada em todas as queries do tab RFV).
    if not df_painel.empty:
        df_plot = df_painel.copy()
        # Total agora soma TODOS os 9 segmentos da matriz RFV (cobre 100% da carteira do vendedor)
        df_plot["total_segmentos"] = (
            df_plot["qtd_campeoes"]
            + df_plot["qtd_fieis"]
            + df_plot["qtd_fieis_potencial"]
            + df_plot["qtd_novos_promessas"]
            + df_plot["qtd_precisando_atencao"]
            + df_plot["qtd_nao_pode_perder"]
            + df_plot["qtd_quase_dormentes"]
            + df_plot["qtd_em_risco_hibernando"]
            + df_plot["qtd_perdidos"]
        )

        # Ordem de empilhamento: do "mais saudável" (base, verde) ao "mais crítico" (topo, vermelho).
        # Cores transitam: verde escuro → verde → verde claro → amarelo → laranja → roxo → vermelho.
        fig_v = go.Figure()
        _bar_line = dict(marker_line_color="rgba(255,255,255,0.35)", marker_line_width=0.6)
        fig_v.add_trace(go.Bar(name="Campeões",              x=df_plot["rfv_salesperson"], y=df_plot["qtd_campeoes"],              marker_color="#0D5C4A", **_bar_line))
        fig_v.add_trace(go.Bar(name="Fiéis",                 x=df_plot["rfv_salesperson"], y=df_plot["qtd_fieis"],                 marker_color="#1B7A40", **_bar_line))
        fig_v.add_trace(go.Bar(name="Fiéis em Potencial",    x=df_plot["rfv_salesperson"], y=df_plot["qtd_fieis_potencial"],       marker_color="#4C9A5A", **_bar_line))
        fig_v.add_trace(go.Bar(name="Novos / Promessas",     x=df_plot["rfv_salesperson"], y=df_plot["qtd_novos_promessas"],       marker_color="#A3D977", **_bar_line))
        fig_v.add_trace(go.Bar(name="Precisando de Atenção", x=df_plot["rfv_salesperson"], y=df_plot["qtd_precisando_atencao"],    marker_color="#FCD34D", **_bar_line))
        fig_v.add_trace(go.Bar(name="Quase Dormentes",       x=df_plot["rfv_salesperson"], y=df_plot["qtd_quase_dormentes"],       marker_color="#FB923C", **_bar_line))
        fig_v.add_trace(go.Bar(name="Não Pode Perder",       x=df_plot["rfv_salesperson"], y=df_plot["qtd_nao_pode_perder"],       marker_color="#6D28D9", **_bar_line))
        fig_v.add_trace(go.Bar(name="Em Risco + Hibernando", x=df_plot["rfv_salesperson"], y=df_plot["qtd_em_risco_hibernando"],   marker_color="#EA580C", **_bar_line))
        fig_v.add_trace(go.Bar(name="Perdidos",              x=df_plot["rfv_salesperson"], y=df_plot["qtd_perdidos"],              marker_color="#991B1B", **_bar_line))
        # Offset do rótulo do total proporcional ao maior valor (não fixo +8), senão
        # corta na SAC (números pequenos). Eixo Y ganha headroom pro rótulo caber.
        _ymax = int(df_plot["total_segmentos"].max()) if not df_plot["total_segmentos"].empty else 0
        _lbl_off = max(_ymax * 0.05, 2)
        fig_v.add_trace(go.Scatter(
            x=df_plot["rfv_salesperson"],
            y=df_plot["total_segmentos"] + _lbl_off,
            text=df_plot["total_segmentos"].astype(int).astype(str),
            mode="text",
            textfont=dict(color="#111827", size=12, family="Arial Black"),
            showlegend=False,
            hoverinfo="skip",
        ))
        fig_v.update_layout(
            barmode="stack",
            height=370,
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0),
            margin=dict(l=8, r=8, t=48, b=6),
            bargap=0.22,
            xaxis=dict(title="", tickfont=dict(size=12)),
            yaxis=dict(title="", showgrid=False, showticklabels=False, zeroline=False,
                       range=[0, _ymax * 1.18 + 2]),
        )
        st.plotly_chart(fig_v, use_container_width=True)

        section_title("Visão CRM por Carteira")
        df_tbl = df_painel[[
            "rfv_salesperson", "qtd_clientes_carteira",
            "faturamento", "ticket_medio",
            "crm_deals_open", "pipeline_crm",
            "alertas_oportunidade", "alertas_churn", "clientes_fora_radar",
        ]].rename(columns={
            "rfv_salesperson": "Carteira",
            "qtd_clientes_carteira": "Clientes",
            "faturamento": "Fat. ERP (R$)",
            "ticket_medio": "Ticket Médio",
            "crm_deals_open": "CRM Deals",
            "pipeline_crm": "Pipeline CRM",
            "alertas_oportunidade": "Oport. sem CRM",
            "alertas_churn": "Churn Silencioso",
            "clientes_fora_radar": "Fora do Radar",
        })
        # Formatação BRL (separador de milhar + R$). Fat/Pipeline sem centavos;
        # Ticket com centavos. Inteiros (clientes/deals/alertas) com separador de milhar.
        df_tbl["Clientes"]       = df_tbl["Clientes"].apply(lambda v: fmt_num(float(v), 0))
        df_tbl["Fat. ERP (R$)"]  = df_tbl["Fat. ERP (R$)"].apply(lambda v: "R$ " + fmt_num(float(v), 0))
        df_tbl["Ticket Médio"]   = df_tbl["Ticket Médio"].apply(lambda v: fmt_brl(float(v)))
        df_tbl["Pipeline CRM"]   = df_tbl["Pipeline CRM"].apply(lambda v: "R$ " + fmt_num(float(v), 0))
        df_tbl["CRM Deals"]      = df_tbl["CRM Deals"].apply(lambda v: fmt_num(float(v), 0))
        st.dataframe(df_tbl, use_container_width=True, hide_index=True)

    section_title("Alertas de Inteligência Comercial")

    ALERT_META = {
        "OPORTUNIDADE_SEM_CRM":  ("", "Oportunidade sem CRM", "warning",
                                   "Clientes topo (Campeões/Fiéis/NPP) sem deal ativo no Pipedrive."),
        "CHURN_SILENCIOSO":      ("", "Churn Silencioso", "danger",
                                   "Em Risco/Hibernando sem deal e sem contato há 60d+."),
        "RECUPERACAO_ANDAMENTO": ("", "Recuperação em Andamento", "success",
                                   "Em Risco/Hibernando com deal aberto, sinal positivo de reativação."),
        "REATIVACAO_ALTO_VALOR": ("", "Reativação Alto Valor", "warning",
                                   "Perdidos com faturamento histórico acima de R$ 50k."),
        "FORA_DO_RADAR_CRM":     ("", "Fora do Radar CRM", "danger",
                                   "Clientes ativos no ERP sem correspondência no Pipedrive."),
    }

    if not df_alertas.empty:
        cols_a = st.columns(min(len(df_alertas), 5))
        for i, (_, ar) in enumerate(df_alertas.iterrows()):
            if i >= 5:
                break
            meta = ALERT_META.get(ar["tipo_alerta"], ("", ar["tipo_alerta"], "", ""))
            with cols_a[i]:
                kpi_card(
                    label=f"{meta[0]} {meta[1]}",
                    value=f'{int(ar["qtd"])} clientes',
                    delta=fmt_brl(float(ar["valor_total"])),
                    delta_dir="flat",
                    variant=meta[2],
                )
        st.markdown("<br>", unsafe_allow_html=True)
        for _, ar in df_alertas.iterrows():
            meta = ALERT_META.get(ar["tipo_alerta"], ("", ar["tipo_alerta"], "", ""))
            st.markdown(
                f"<small><b>{meta[0]} {meta[1]}:</b> {meta[3]}</small>",
                unsafe_allow_html=True,
            )

        # ── Drill-down dos alertas: seleciona um tipo e ve a lista de clientes ──
        st.markdown("<br>", unsafe_allow_html=True)
        section_title("Detalhe do Alerta — Clientes para Acionar")

        alert_tipos_disponiveis = df_alertas["tipo_alerta"].tolist()
        alert_labels = {
            t: f'{ALERT_META.get(t, ("", t, "", ""))[0]} {ALERT_META.get(t, ("", t, "", ""))[1]}'
            for t in alert_tipos_disponiveis
        }
        ad_c1, _ad_c2 = st.columns([3, 5])
        with ad_c1:
            tipo_alerta_sel = st.selectbox(
                "Tipo de alerta",
                options=alert_tipos_disponiveis,
                format_func=lambda t: alert_labels.get(t, t),
                key="rfv_alerta_tipo",
            )

        if tipo_alerta_sel:
            with st.spinner("Carregando clientes do alerta..."):
                try:
                    # Drill-down deduplicado por NOME da empresa.
                    # Para cada empresa: agrega filiais (partner_codes), familias (SAC/HOSPITALAR),
                    # vendedores. Cruza com param_com_entity_bridge para status no Pipedrive.
                    df_alerta_det = query(f"""
                        WITH base AS (
                            SELECT
                                UPPER(TRIM(partner_name)) AS nome_norm,
                                ANY_VALUE(partner_name) AS nome_cliente,
                                STRING_AGG(DISTINCT CAST(partner_code AS STRING), ', ' ORDER BY CAST(partner_code AS STRING)) AS filiais_codes,
                                COUNT(DISTINCT partner_code) AS qtd_filiais,
                                STRING_AGG(DISTINCT rfv_familia, ' + ' ORDER BY rfv_familia) AS familias,
                                STRING_AGG(DISTINCT {SP_DISPLAY}, ', ' ORDER BY {SP_DISPLAY}) AS vendedores,
                                STRING_AGG(DISTINCT segmento_rfv, ', ' ORDER BY segmento_rfv) AS segmentos,
                                MAX(faturamento_periodo) AS faturamento,
                                MAX(qtd_deals_open) AS deals_abertos,
                                MAX(valor_pipeline_open) AS pipeline_crm,
                                MIN(dias_sem_deal_crm) AS dias_sem_deal,
                                ANY_VALUE(descricao_alerta) AS descricao
                            FROM `{GOLD_COM}.gold_com_alerta_comercial`
                            WHERE tipo_alerta = '{tipo_alerta_sel}'
                              AND rfv_salesperson NOT LIKE 'Eduardo%'
                              AND rfv_salesperson NOT LIKE 'Karina%'
                              {fam_alerta}
                            GROUP BY 1
                        ),
                        bridge_agg AS (
                            SELECT
                                UPPER(TRIM(partner_name)) AS nome_norm,
                                MAX(IF(org_id IS NOT NULL, 1, 0)) AS tem_crm,
                                STRING_AGG(DISTINCT CAST(org_id AS STRING), ', ') AS orgs_crm,
                                STRING_AGG(DISTINCT org_name, ', ') AS nomes_crm
                            FROM `{PROJ}.silver_comercial.param_com_entity_bridge`
                            WHERE partner_name IS NOT NULL
                            GROUP BY 1
                        )
                        SELECT
                            b.nome_cliente,
                            b.familias,
                            b.qtd_filiais AS filiais,
                            b.vendedores,
                            b.segmentos,
                            ROUND(b.faturamento, 2) AS faturamento,
                            b.deals_abertos,
                            ROUND(b.pipeline_crm, 2) AS pipeline_crm,
                            b.dias_sem_deal,
                            CASE WHEN br.tem_crm = 1 THEN 'Sim' ELSE 'Não' END AS no_crm,
                            COALESCE(br.nomes_crm, '—') AS org_pipedrive,
                            b.descricao
                        FROM base b
                        LEFT JOIN bridge_agg br USING (nome_norm)
                        ORDER BY b.faturamento DESC
                    """)

                    if not df_alerta_det.empty:
                        meta = ALERT_META.get(tipo_alerta_sel, ("", tipo_alerta_sel, "", ""))
                        _qtd = len(df_alerta_det)
                        _fat = float(df_alerta_det["faturamento"].sum())
                        _a1, _a2, _a3 = st.columns(3)
                        with _a1:
                            kpi_card(f"{meta[0]} {meta[1]}", f"{_qtd} cliente{'s' if _qtd != 1 else ''}", variant=meta[2])
                        with _a2:
                            kpi_card("Faturamento do grupo", fmt_brl(_fat))
                        with _a3:
                            _tk = _fat / _qtd if _qtd else 0
                            kpi_card("Ticket médio", fmt_brl(_tk))

                        df_alerta_show = df_alerta_det.rename(columns={
                            "nome_cliente": "Cliente",
                            "familias": "Famílias",
                            "filiais": "Filiais",
                            "vendedores": "Carteira(s)",
                            "segmentos": "Segmento(s) RFV",
                            "faturamento": "Faturamento (R$)",
                            "deals_abertos": "Deals Abertos",
                            "pipeline_crm": "Pipeline CRM (R$)",
                            "dias_sem_deal": "Dias sem Deal",
                            "no_crm": "Existe no CRM?",
                            "org_pipedrive": "Org. Pipedrive",
                            "descricao": "Descrição",
                        })
                        st.dataframe(
                            df_alerta_show,
                            width="stretch",
                            hide_index=True,
                            column_config={
                                "Faturamento (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                "Pipeline CRM (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                                "Dias sem Deal": st.column_config.NumberColumn(format="%d dias"),
                                "Deals Abertos": st.column_config.NumberColumn(format="%d"),
                                "Filiais": st.column_config.NumberColumn(format="%d"),
                            },
                        )
                    else:
                        st.info("Nenhum cliente neste alerta com os filtros atuais.")
                except Exception as _e_alert:
                    st.error(f"Erro ao carregar detalhes do alerta: {_e_alert}")

# ── Venda Diária ─────────────────────────────────────────────
with tab_diaria:
    # Aba "Gestão à Vista" — substitui o antigo mockup "Venda Diária" (decisão 15/06).
    # Painel completo (meta, ritmo, ranking %, pipeline, atividades) em utils/gestao_vista_view.
    from dashboard.utils import gestao_vista_view
    gestao_vista_view.render(key_prefix="gv_tab")

st.markdown("---")
st.caption("gold_comercial + silver_comercial (RFV) · sapient-metrics-492914-m7")
