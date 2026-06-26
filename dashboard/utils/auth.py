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


def require_login():
    """Bloqueia a página se não autenticado. No-op se auth não configurado."""
    email_ok, pwd_ok = _configured_creds()
    if not pwd_ok:
        return  # auth ainda não configurado → app aberto (sem regressão)
    if st.session_state.get("_auth_ok"):
        return

    st.markdown("<div style='max-width:420px;margin:10vh auto 0;'>", unsafe_allow_html=True)
    st.markdown("### Dashboard Nevoni — acesso restrito")
    st.caption("Use o e-mail e a senha enviados no grupo.")
    with st.form("login_form"):
        email = st.text_input("E-mail")
        pwd = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

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
