"""Abertura da interface: configuração da página, CSS e scripts.

O visual fica em assets/: estilo.css (tokens e componentes) e um .js por comportamento.
"""

import logging
import os

import streamlit as st

from iana.config import DIRETORIO_ICONES

logger = logging.getLogger(__name__)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _ler(nome: str) -> str:
    with open(os.path.join(ASSETS, nome), encoding="utf-8") as f:
        return f.read()


def _encontrar_icone() -> str | None:
    candidatos = [
        "android-chrome-512x512.png",
        "android-chrome-192x192.png",
        "apple-touch-icon.png",
        "favicon-32x32.png",
        "favicon.png",
        "favicon.ico",
        "logo.png",
        "icon.png",
    ]
    for nome in candidatos:
        caminho = os.path.join(DIRETORIO_ICONES, nome)
        if os.path.exists(caminho):
            return caminho
    return None


ICONE_FAVICON = _encontrar_icone()


# =============================================================================
# Inicialização
# =============================================================================
def inicializar_interface() -> None:
    favicon = ICONE_FAVICON if ICONE_FAVICON else None
    st.set_page_config(page_title="iAna", page_icon=favicon, layout="wide")
    # CSS via st.html vai para um container de eventos e não ocupa espaço.
    st.html("<style>" + _ler("estilo.css") + "</style>")
    # Scripts rodam direto na página, sem iframes (components.v1.html está
    # obsoleto). Cada script se protege contra reexecução nos reruns.
    st.html(
        "<script>"
        + _ler("tema.js").replace("__TEMA__", st.context.theme.type or "")
        + "</script><script>"
        + _ler("sidebar.js")
        + "</script><script>"
        + _ler("navegacao.js")
        + "</script><script>"
        + _ler("copiar.js")
        + "</script>",
        unsafe_allow_javascript=True,
    )
