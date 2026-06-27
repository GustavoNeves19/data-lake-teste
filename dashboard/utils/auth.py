"""Gate de acesso simples (e-mail + senha compartilhados) para o dashboard.

A credencial fica em st.secrets["auth"] — NUNCA no repositório.
- Local:  .streamlit/secrets.toml  (gitignored)
- Cloud:  Streamlit Cloud → Settings → Secrets

    [auth]
    email = "acesso@nevoni.com.br"
    password = "..."

Enquanto a senha não estiver configurada, o app NÃO bloqueia (evita lockout no
deploy). A sessão é mantida via st.session_state, então o login vale para todas
as páginas até o usuário sair ou fechar a aba.
"""
import streamlit as st


def _configured_creds():
    """Lê (email, senha) de st.secrets['auth']. Retorna ('','') se não configurado."""
    try:
        a = st.secrets["auth"]
        return str(a.get("email", "")).strip(), str(a.get("password", ""))
    except Exception:
        return "", ""


# Identidade visual da tela de acesso (espelha a paleta da marca Nevoni:
# índigo #1E1882 + emerald #10B981). Estilo de cartão central sobre fundo cheio,
# no padrão das telas de login do grupo (ex.: Nativa360).
_LOGIN_CSS = """
<style>
/* fundo cheio índigo + esconde o chrome do app durante o login */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
header[data-testid="stHeader"], #MainMenu, footer, .stDeployButton { display: none !important; }
[data-testid="stAppViewContainer"] {
    background: radial-gradient(120% 120% at 50% 0%, #2A2496 0%, #1E1882 45%, #15104F 100%) !important;
}
.main .block-container { padding-top: 0 !important; max-width: 520px !important; }

/* o próprio st.form vira o cartão branco central */
[data-testid="stForm"] {
    background: #FFFFFF;
    border: none;
    border-radius: 20px;
    padding: 40px 38px 34px 38px !important;
    margin: 13vh auto 0 auto;
    max-width: 430px;
    box-shadow: 0 24px 60px rgba(10, 8, 50, 0.45);
}

/* marca dentro do cartão */
.login-brand { text-align: center; margin-bottom: 26px; }
.login-brand .logo {
    width: 84px; height: 84px; display: block; margin: 0 auto 16px auto;
    filter: drop-shadow(0 8px 18px rgba(30, 24, 130, 0.28));
}
.login-brand .t { font-size: 22px; font-weight: 700; color: #15151F; margin: 0; letter-spacing: -.02em; }
.login-brand .s { font-size: 13px; color: #8A8A99; margin: 3px 0 0 0; }

/* inputs do cartão */
[data-testid="stForm"] label { color: #15151F !important; font-weight: 600; font-size: 13px; }
[data-testid="stForm"] [data-baseweb="input"] {
    background: #F4F5FB; border-radius: 10px; border: 1px solid #E6E7F2;
}
[data-testid="stForm"] [data-baseweb="input"]:focus-within {
    border-color: #1E1882; box-shadow: 0 0 0 3px rgba(30,24,130,.12);
}
[data-testid="stForm"] input { color: #15151F !important; }

/* botão Entrar — cheio, gradiente da marca */
[data-testid="stForm"] .stButton > button,
[data-testid="stForm"] [data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #1E1882 0%, #3A33B8 100%) !important;
    color: #fff !important; border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; font-size: 15px !important; padding: 11px 0 !important;
    margin-top: 8px; box-shadow: 0 8px 18px rgba(30,24,130,.28);
    transition: filter .15s, transform .05s;
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] > button:hover { filter: brightness(1.08); }
[data-testid="stForm"] [data-testid="stFormSubmitButton"] > button:active { transform: translateY(1px); }

.login-foot { text-align: center; color: rgba(255,255,255,.55); font-size: 12px; margin-top: 18px; }
</style>
"""


def require_login():
    """Bloqueia a página se não autenticado. No-op se auth não configurado."""
    email_ok, pwd_ok = _configured_creds()
    if not pwd_ok:
        return  # auth ainda não configurado → app aberto (sem regressão)
    if st.session_state.get("_auth_ok"):
        return

    from dashboard.utils.branding import logo_data_uri

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)
    with st.form("login_form"):
        st.markdown(
            f"""
            <div class="login-brand">
                <img class="logo" src="{logo_data_uri('logo')}" alt="Nevoni"/>
                <p class="t">Dashboard Nevoni</p>
                <p class="s">Gestão 360°</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        email = st.text_input("E-mail", placeholder="seu.email@nevoni.com.br")
        pwd = st.text_input("Senha", type="password", placeholder="••••••••")
        entrar = st.form_submit_button("Entrar", use_container_width=True)
    st.markdown(
        '<p class="login-foot">Nevoni · Powered by VanguardIA</p>',
        unsafe_allow_html=True,
    )

    if entrar:
        email_match = (not email_ok) or (email.strip().lower() == email_ok.lower())
        if email_match and pwd == pwd_ok:
            st.session_state["_auth_ok"] = True
            st.rerun()
        else:
            st.error("E-mail ou senha incorretos.")
    st.stop()


def logout_button():
    """Botão 'Sair' na sidebar (só aparece quando logado e auth configurado)."""
    _, pwd_ok = _configured_creds()
    if pwd_ok and st.session_state.get("_auth_ok"):
        if st.sidebar.button("Sair", key="_logout_btn", use_container_width=True):
            st.session_state["_auth_ok"] = False
            st.rerun()


# ── Permissão de EDIÇÃO de meta (2º nível, reunião 26/06) ─────────────────────
# Liberada só para os e-mails da liderança (Vinícius + Ops). Credencial em
# st.secrets["meta_editor"] — Gustavo preenche no Streamlit Cloud, NUNCA no repo:
#
#     [meta_editor]
#     emails   = "vinicius@...,ops@..."   # lista separada por vírgula
#     password = "..."
#
# Enquanto não estiver configurado, a edição simplesmente não aparece (sem regressão).

def _editor_creds():
    """Lê (emails_permitidos, senha) de st.secrets['meta_editor']. ([], '') se ausente."""
    try:
        a = st.secrets["meta_editor"]
        emails = [e.strip().lower() for e in str(a.get("emails", "")).split(",") if e.strip()]
        return emails, str(a.get("password", ""))
    except Exception:
        return [], ""


def meta_editor_enabled() -> bool:
    """True se a edição de meta está configurada (há senha em secrets)."""
    _, pwd = _editor_creds()
    return bool(pwd)


def current_meta_editor():
    """E-mail do editor logado nesta sessão (ou None)."""
    return st.session_state.get("_meta_editor_email")


def check_meta_editor(email: str, pwd: str) -> bool:
    """Valida e-mail (na allowlist) + senha de edição."""
    emails, pwd_ok = _editor_creds()
    if not pwd_ok:
        return False
    return email.strip().lower() in emails and pwd == pwd_ok
