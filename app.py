"""
iAna — Assistente Pessoal de IA Local.
Orquestrador Principal (App Entry Point).
"""

import os
import streamlit as st

from config import DIRETORIO_HISTORICO, DIRETORIO_AUDIO, DIRETORIO_MEMORIA
from storage import (
    garantir_estado_inicial, carregar_conversa, limpar_audios_orfaos, exibir_avisos_pendentes
)
from ui import (
    inicializar_interface, renderizar_sidebar, renderizar_input_chat,
    exibir_boas_vindas, renderizar_mensagens_anteriores
)
from processor import processar_resposta
from brain import aquecer_modelos

def _processar_carregamento_conversa() -> None:
    """
    Se a URL contém ?load_conv=..., carrega essa conversa e reroda.
    Chamado ANTES de renderizar a sidebar, para o estado já estar correto.
    """
    c_id = st.query_params.get("load_conv")
    if not c_id:
        return

    st.query_params.clear()
    dados = carregar_conversa(c_id)
    st.session_state.id_conversa_atual = c_id
    st.session_state.projeto_atual = dados.get("projeto", "Geral")
    st.session_state.resumo_conversa = dados.get("resumo", "")
    st.session_state.nome_conversa = dados.get("nome")
    st.session_state._resumo_futuro = None
    st.session_state.mensagens = dados.get("mensagens", [])
    st.session_state._ultimo_resumo_em = len(st.session_state.mensagens)
    st.session_state._pendente_processar = False
    st.session_state.ultima_foi_voz = False
    st.session_state.anexo_pendente = None
    st.session_state.documento_ativo = None
    st.session_state._anexo_ja_processado = None
    st.session_state._pedido_com_anexo = None
    st.session_state._uploader_version = st.session_state.get("_uploader_version", 0) + 1
    st.session_state._mic_version = st.session_state.get("_mic_version", 0) + 1
    st.rerun()

def main() -> None:
    inicializar_interface()

    for d in (DIRETORIO_HISTORICO, DIRETORIO_AUDIO, DIRETORIO_MEMORIA):
        os.makedirs(d, exist_ok=True)

    garantir_estado_inicial()
    aquecer_modelos()
    if not st.session_state.get("_audios_orfaos_limpos"):
        st.session_state._audios_orfaos_limpos = True
        limpar_audios_orfaos()
    _processar_carregamento_conversa()

    estado = renderizar_sidebar()

    if st.session_state.mensagens:
        renderizar_mensagens_anteriores()

        if (
            st.session_state.get("_pendente_processar")
            and st.session_state.mensagens[-1]["role"] == "user"
        ):
            st.session_state._pendente_processar = False
            processar_resposta(estado, modo_voz=st.session_state.get("ultima_foi_voz", False))
            st.session_state.ultima_foi_voz = False
            st.rerun()
    else:
        exibir_boas_vindas()

    renderizar_input_chat()
    # No fim: só chega aqui um ciclo que não foi interrompido por st.rerun,
    # então o aviso fica visível.
    exibir_avisos_pendentes()

if __name__ == "__main__":
    main()