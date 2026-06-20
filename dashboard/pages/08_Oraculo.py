"""
Oráculo da Nevoni — Assistente IA sobre o Data Lake
"""

import streamlit as st

st.set_page_config(
    page_title="Oráculo da Nevoni",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dashboard.utils.components import inject_css, sidebar_brand
from dashboard.utils.oracle import oracle_ask, oracle_is_ready

inject_css()
sidebar_brand()

# ── Sidebar: input da chave OpenAI ────────────────────────────────────────────
with st.sidebar:
    # Chave vem do Secret (produção) → nada de chave aparece pro executivo.
    # O campo só surge se NÃO houver chave (dev/fallback), pra colar na sessão.
    if not oracle_is_ready():
        st.markdown("### Chave OpenAI")
        key_input = st.text_input(
            "Cole `sk-...`",
            type="password",
            key="openai_api_key_input",
            help="Sua chave fica só nesta sessão do navegador",
        )
        if key_input:
            st.session_state["openai_api_key"] = key_input
            st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="
        background: linear-gradient(135deg, #0D0B50 0%, #1E1882 60%, #4A3FD0 100%);
        border-radius: 16px;
        padding: 32px 40px;
        margin-bottom: 24px;
        border-left: 5px solid #10B981;
    ">
        <div style="display:flex; align-items:center; gap:16px; margin-bottom:12px;">
            <div style="
                width:48px; height:48px; border-radius:12px;
                background: rgba(16,185,129,0.2);
                border: 1px solid rgba(16,185,129,0.4);
                display:flex; align-items:center; justify-content:center;
                font-size:24px; font-weight:900; color:#6EE7B7;
            ">N</div>
            <div>
                <p style="color:rgba(255,255,255,0.5); font-size:11px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin:0;">Nevoni · Data Lake Intelligence</p>
                <h1 style="color:white; margin:4px 0 0; font-size:26px; font-weight:800; letter-spacing:-.5px;">Oráculo da Nevoni</h1>
            </div>
        </div>
        <p style="color:rgba(255,255,255,0.55); margin:0; font-size:14px; line-height:1.6; max-width:680px;">
            Motor de inteligência analítica da Nevoni — transforma dados do Data Lake em decisões estratégicas através de linguagem natural. Acesso direto às tabelas Silver e Gold do BigQuery.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Verificação de chave ──────────────────────────────────────────────────────
if not oracle_is_ready():
    st.info(
        "**O Oráculo aguarda sua chave.**\n\n"
        "Cole sua chave OpenAI (`sk-...`) na sidebar para ativar o chat.",
        icon="",
    )
    st.stop()

# ── Histórico de mensagens ────────────────────────────────────────────────────
if "oracle_messages" not in st.session_state:
    st.session_state.oracle_messages = []

# Mensagem de boas-vindas (apenas se histórico vazio)
if not st.session_state.oracle_messages:
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #EEF0FF 0%, #F5F3FF 100%);
            border-left: 4px solid #1E1882;
            border-radius: 10px;
            padding: 18px 22px;
            margin-bottom: 20px;
        ">
            <p style="margin:0; font-size:14px; color:#1E1882; font-weight:700;">
                Os dados estão prontos. O que deseja saber?
            </p>
            <p style="margin:8px 0 0; font-size:13px; color:#374151;">
                Exemplos de perguntas:
            </p>
            <ul style="margin:6px 0 0; font-size:13px; color:#374151; padding-left:20px;">
                <li>Quem são os 10 Campeões do HOSPITALAR em abril/2026?</li>
                <li>Qual vendedor das 4 carteiras tem mais clientes em risco?</li>
                <li>Quantos Novos Clientes apareceram e qual o faturamento deles?</li>
                <li>Quem são os clientes ociosos (na carteira mas sem compra) do Guilherme Aquino?</li>
                <li>Compare o ticket médio das 4 carteiras Hospitalar em abril/2026</li>
                <li>Quais Novos Clientes já são Campeões? (alta prioridade pra alocar)</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Renderiza histórico de chat
for msg in st.session_state.oracle_messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])

# ── Input de chat (fixo no rodapé da página) ─────────────────────────────────
if prompt := st.chat_input("Pergunte ao Oráculo sobre os dados da Nevoni..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("O Oráculo está consultando os dados..."):
            resposta = oracle_ask(prompt)
        st.markdown(resposta)

# ── Botão limpar conversa ─────────────────────────────────────────────────────
if st.session_state.oracle_messages:
    st.markdown("<br>", unsafe_allow_html=True)
    col_clear, _ = st.columns([1, 4])
    with col_clear:
        if st.button("Limpar conversa", use_container_width=True):
            st.session_state.oracle_messages = []
            st.rerun()
