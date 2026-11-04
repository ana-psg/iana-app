"""Barra lateral: projetos, lista de conversas e ações de histórico e memória."""

import html
import logging
from datetime import datetime
from urllib.parse import quote

import streamlit as st

from iana.brain import apagar_toda_memoria
from iana.storage import (
    apagar_todo_historico,
    carregar_metadados_conversas,
    criar_nova_sessao,
    listar_conversas_cached,
    obter_nome_exibicao,
    salvar_conversa,
)

logger = logging.getLogger(__name__)

_SVG_CHAT = (
    '<svg class="conv-icon" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
    "</svg>"
)


def _agrupar_conversas(conversas: list[str], dados_conv: dict, proj_ativo: str) -> tuple[list[str], list[str]]:
    recentes, antigas = [], []
    hoje = datetime.now().date()
    for c_id in [c for c in conversas if dados_conv[c].get("projeto", "Geral") == proj_ativo]:
        try:
            data = datetime.strptime(c_id[:8], "%Y%m%d").date()
            (recentes if (hoje - data).days <= 7 else antigas).append(c_id)
        except ValueError:  # id sem data no começo (conversas antigas)
            recentes.append(c_id)
    return recentes, antigas


def _renderizar_bloco(titulo: str, ids: list[str], dados_conv: dict) -> None:
    ativo = st.session_state.get("id_conversa_atual")
    itens = []
    for c_id in ids:
        nome = html.escape(obter_nome_exibicao(dados_conv[c_id], c_id))
        id_url = quote(c_id, safe="")
        classe = "conv-item active" if c_id == ativo else "conv-item"
        itens.append(
            f'<a class="{classe}" href="?load_conv={id_url}" data-conv-id="{id_url}">'
            f"{_SVG_CHAT}"
            f'<span class="conv-name">{nome}</span>'
            f"</a>"
        )
    html_bloco = (
        f'<div class="conv-block">'
        f'<div class="conv-group">{titulo} <span class="chev">⌄</span></div>'
        f'<div class="conv-list">{"".join(itens)}</div>'
        f"</div>"
    )
    st.markdown(html_bloco, unsafe_allow_html=True)


# =============================================================================
# Sidebar
# =============================================================================
def _ao_trocar_projeto() -> None:
    # Callback roda antes do script: a troca já está feita quando a
    # sidebar for desenhada, sem rerun extra.
    criar_nova_sessao(st.session_state.select_projeto)


@st.dialog("Apagar todo o histórico?")
def _confirmar_apagar_historico() -> None:
    n = len(listar_conversas_cached())
    st.markdown(
        f"Isso apaga **{n} conversa{'s' if n != 1 else ''}** de todos os projetos "
        "e os áudios das respostas. Não dá para desfazer."
    )
    apagar_memoria = st.checkbox(
        "Apagar também os documentos memorizados",
        help="A memória guarda o conteúdo dos documentos enviados, usado para responder perguntas sobre eles.",
    )
    col_cancelar, col_apagar = st.columns(2)
    if col_cancelar.button("Cancelar", use_container_width=True):
        st.rerun()
    if col_apagar.button("Apagar", type="primary", use_container_width=True):
        apagar_todo_historico()
        if apagar_memoria:
            apagar_toda_memoria()
            st.session_state.documento_ativo = None
        criar_nova_sessao(st.session_state.get("projeto_atual", "Geral"))
        st.rerun()


def renderizar_sidebar() -> dict:
    with st.sidebar:
        with st.container(key="nav_trigger_hidden"):
            st.button("nav", key="nav_trigger_hidden_btn")

        if st.button("＋  Nova conversa", use_container_width=True, type="primary"):
            criar_nova_sessao(st.session_state.get("projeto_atual", "Geral"))
            st.rerun()

        pesquisa_web = st.toggle("Autonomia de Pesquisa", value=True)

        st.markdown(
            '<hr style="border:none; border-top:1px solid var(--border-subtle); margin:1rem 0 1.1rem 0;">',
            unsafe_allow_html=True,
        )

        novo_proj = st.text_input(
            "Novo projeto", placeholder="Nome do projeto...", label_visibility="collapsed", key="input_novo_projeto"
        )
        if st.button("Adicionar Projeto", use_container_width=True, type="secondary") and novo_proj:
            st.session_state.projeto_atual = novo_proj
            criar_nova_sessao(novo_proj)
            salvar_conversa(st.session_state.id_conversa_atual, [], None, novo_proj, "")
            st.rerun()

        conversas = listar_conversas_cached()
        dados_conv = carregar_metadados_conversas(conversas)
        conversas = [c for c in conversas if c in dados_conv]
        projeto_atual = st.session_state.get("projeto_atual", "Geral")
        projetos = sorted(set(["Geral", projeto_atual] + [d.get("projeto", "Geral") for d in dados_conv.values()]))

        st.markdown(
            '<div style="font-size:12.5px; font-weight:600; color:var(--text-secondary); '
            'margin:14px 0 4px 0;">Projetos:</div>',
            unsafe_allow_html=True,
        )
        # O selectbox sempre espelha projeto_atual. Antes, o valor guardado
        # pela key prevalecia sobre o index e desfazia "Adicionar Projeto".
        st.session_state.select_projeto = projeto_atual
        st.selectbox(
            "Projetos",
            projetos,
            label_visibility="collapsed",
            key="select_projeto",
            on_change=_ao_trocar_projeto,
        )
        proj_ativo = projeto_atual

        with st.expander(f"Conversas ({proj_ativo})", expanded=True):
            recentes, antigas = _agrupar_conversas(conversas, dados_conv, proj_ativo)
            if recentes or antigas:
                if recentes:
                    _renderizar_bloco("Recentes", recentes, dados_conv)
                if antigas:
                    _renderizar_bloco("Anteriores", antigas, dados_conv)
            else:
                st.markdown('<div class="conv-empty">Nenhuma conversa ainda.</div>', unsafe_allow_html=True)

        st.markdown(
            '<hr style="border:none; border-top:1px solid var(--border-subtle); margin:1.1rem 0;">',
            unsafe_allow_html=True,
        )
        if st.button("Apagar todo o histórico", use_container_width=True, type="secondary"):
            _confirmar_apagar_historico()

    return {"pesquisa_web": pesquisa_web}


# =============================================================================
# Botão copiar resposta
# =============================================================================
