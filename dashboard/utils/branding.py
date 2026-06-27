"""Identidade visual da Nevoni — caminhos dos assets de marca + helpers.

A logo oficial (círculo índigo + anel branco + "ni") vive em `dashboard/assets/`
como PNG de alta resolução, gerada a partir do master vetorial. Use:

    from dashboard.utils.branding import FAVICON
    st.set_page_config(..., page_icon=FAVICON)

    from dashboard.utils.branding import logo_data_uri
    st.markdown(f'<img src="{logo_data_uri()}" width="76">', unsafe_allow_html=True)
"""
from functools import lru_cache
from pathlib import Path
import base64

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

FAVICON  = str(_ASSETS / "nevoni_favicon.png")   # 256px — page_icon
LOGO_PNG = str(_ASSETS / "nevoni_logo.png")      # 1024px — master


@lru_cache(maxsize=None)
def logo_data_uri(variant: str = "logo") -> str:
    """Data URI base64 do PNG (embute o asset direto no HTML, sem servir arquivo).

    variant: 'logo' (512px, p/ o card de login) ou 'favicon' (256px, p/ sidebar).
    """
    name = "nevoni_logo_512.png" if variant == "logo" else "nevoni_favicon.png"
    b64 = base64.b64encode((_ASSETS / name).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"
