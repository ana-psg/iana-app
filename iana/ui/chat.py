"""Área da conversa: boas-vindas, mensagens, respostas, anexos, voz e caixa de mensagem."""

import base64
import html
import logging
import re

import streamlit as st

from iana.brain import adicionar_a_memoria, remover_da_memoria
from iana.config import EXTENSOES_DOC, EXTENSOES_IMG, NOME_USUARIO
from iana.media import extrair_conteudo_documento, processar_imagem_otimizada, transcrever_audio
from iana.storage import avisar, caminho_audio, imagens_da_mensagem

logger = logging.getLogger(__name__)

_MAPA_IDIOMA_UI = {
    "PT": "pt",
    "EN": "en",
    "ES": "es",
    "FR": "fr",
}
_OPCOES_IDIOMA = ["Auto", "PT", "EN", "ES", "FR"]


def _renderizar_botao_copiar(texto: str) -> None:
    # O texto bruto (markdown) fica num textarea oculto; o SCRIPT_COPIAR,
    # carregado uma vez, copia ao clicar. html.escape impede que a resposta
    # do modelo vire HTML.
    st.html(
        '<div class="iana-copy">'
        f'<textarea class="iana-raw" hidden>{html.escape(texto)}</textarea>'
        '<button class="iana-copy-btn" type="button">Copiar resposta</button>'
        "</div>"
    )


# =============================================================================
# Resposta formatada
# =============================================================================
def renderizar_resposta_formatada(texto: str) -> None:
    padrao_bloco = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
    pos = 0
    for match in padrao_bloco.finditer(texto):
        antes = texto[pos : match.start()].strip()
        if antes:
            st.markdown(antes)
        st.code(match.group(2).rstrip("\n"), language=(match.group(1) or "text").lower())
        pos = match.end()
    resto = texto[pos:].strip()
    if resto:
        st.markdown(resto)
    _renderizar_botao_copiar(texto)


# =============================================================================
# Upload de documento
# =============================================================================
def _processar_upload_documento(arq_doc) -> None:
    with st.spinner("Indexando documento..."):
        texto = extrair_conteudo_documento(arq_doc)
        if not texto or not texto.strip():
            avisar(
                f"Não consegui ler o texto de {arq_doc.name}. Se for um PDF escaneado (só imagem), envie como imagem."
            )
            return
        try:
            adicionar_a_memoria(texto, arq_doc.name)
        except Exception as e:
            logger.warning("Falha ao memorizar %s: %s", arq_doc.name, e, exc_info=True)
            avisar(f"Não consegui memorizar {arq_doc.name}. Verifique se o Ollama está rodando.")
            return
        st.session_state.documento_ativo = {"nome": arq_doc.name, "texto": texto}
        avisar(f"Memorizado: {arq_doc.name}", "📄", "short")


# =============================================================================
# Chips de anexos
# =============================================================================
def _renderizar_chips_anexos() -> None:
    doc = st.session_state.get("documento_ativo")
    if not doc:
        return
    with st.container(key="chip_doc"):
        if st.button(f"📄 {doc['nome']}   ✕", key="remover_doc", help="Remover documento da conversa e da memória"):
            remover_da_memoria(doc["nome"])
            st.session_state.documento_ativo = None
            st.rerun()


# =============================================================================
# Seletor de idiomas via st.popover (nativo, clicável)
# =============================================================================
def _renderizar_seletor_idioma() -> None:
    """Usa st.popover nativo — o trigger é um botão real, o painel aceita
    st.button normais. Não depende de JS inline (que é sanitizado pelo
    st.markdown) nem de query params. O label reflete a escolha atual."""
    idioma_atual = st.session_state.get("idioma_stt", "Auto")

    label = "Auto | PT" if idioma_atual == "Auto" else idioma_atual

    with st.popover(label, use_container_width=True):
        for op in _OPCOES_IDIOMA:
            tipo = "primary" if op == idioma_atual else "secondary"
            if st.button(op, key=f"lang_pick_{op}", use_container_width=True, type=tipo):
                st.session_state.idioma_stt = op
                st.rerun()


# =============================================================================
# Tela de boas-vindas
# =============================================================================
_SVG_AVATAR = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round" width="24" height="24">'
    '<path d="M12 3L3 7.5l9 4.5 9-4.5L12 3z"/>'
    '<path d="M3 12l9 4.5L21 12"/>'
    '<path d="M3 16.5L12 21l9-4.5"/>'
    "</svg>"
)


def _preparar_pedido_com_anexo(tipo: str, pedido: str) -> None:
    """Os cards de documento e imagem enviavam o pedido na hora, sem anexo,
    e o modelo respondia "envie a imagem". Agora o pedido espera o arquivo
    e vai junto com ele."""
    st.session_state._pedido_com_anexo = {"tipo": tipo, "pedido": pedido}
    avisar(f"Anexe a {tipo} pelo + na caixa de mensagem e envie.", "📎", "short")
    st.rerun()


def exibir_boas_vindas():
    nome = f", {NOME_USUARIO}" if NOME_USUARIO else ""
    st.markdown(
        '<div class="greeting-wrap">'
        f'<div class="greeting-avatar">{_SVG_AVATAR}</div>'
        f'<h1 class="greeting-title">Olá{nome}. Como posso ajudar hoje?</h1>'
        '<p class="greeting-sub">Pergunte qualquer coisa, envie um documento ou analise uma imagem.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container(key="sug_row"):
        col1, col2, col3 = st.columns(3, gap="small")

        with col1, st.container(key="sug_doc_card"):
            st.markdown(
                '<div class="sug-card">'
                '<div class="sug-icon">📄</div>'
                '<div class="sug-title">Analisar um documento</div>'
                '<div class="sug-desc">Envie um PDF ou DOCX e pergunte qualquer coisa sobre o conteúdo.</div>'
                '<div class="sug-tag">RAG · MEMÓRIA</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Analisar documento", key="sug_doc", use_container_width=True):
                _preparar_pedido_com_anexo("documento", "Resuma o documento que enviei.")

        with col2, st.container(key="sug_img_card"):
            st.markdown(
                '<div class="sug-card">'
                '<div class="sug-icon">🖼️</div>'
                '<div class="sug-title">Analisar uma imagem</div>'
                '<div class="sug-desc">Arraste uma foto e peça uma descrição, tradução ou transcrição.</div>'
                '<div class="sug-tag">VISÃO · MINICPM-V</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Analisar imagem", key="sug_img", use_container_width=True):
                _preparar_pedido_com_anexo("imagem", "Descreva detalhadamente a imagem.")

        with col3, st.container(key="sug_web_card"):
            st.markdown(
                '<div class="sug-card">'
                '<div class="sug-icon">✦</div>'
                '<div class="sug-title">Pesquisar na web</div>'
                '<div class="sug-desc">Pergunte sobre algo atual — cotações, notícias, eventos recentes.</div>'
                '<div class="sug-tag">DUCKDUCKGO</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Pesquisar", key="sug_web", use_container_width=True):
                st.session_state._sugestao = "Qual é a cotação do dólar hoje?"
                st.rerun()


# =============================================================================
# Input de chat
# =============================================================================
def renderizar_input_chat() -> None:
    _renderizar_chips_anexos()

    # Ordem: input grande → mic → idioma. mic à esquerda do idioma.
    col_input, col_mic, col_lang = st.columns([1, 0.11, 0.22], gap="small", vertical_alignment="bottom")

    with col_input:
        pedido_anexo = st.session_state.get("_pedido_com_anexo")
        submissao = st.chat_input(
            f"Anexe a {pedido_anexo['tipo']} pelo + e envie..." if pedido_anexo else "Pergunte qualquer coisa...",
            accept_file="multiple",
            file_type=EXTENSOES_DOC + EXTENSOES_IMG,
        )

    with col_mic, st.container(key="footer_mic"):
        mic_key = f"mic_{st.session_state.get('_mic_version', 0)}"
        audio = st.audio_input("Gravar", label_visibility="collapsed", key=mic_key)

    with col_lang, st.container(key="footer_lang"):
        _renderizar_seletor_idioma()

    idioma_atual = st.session_state.get("idioma_stt", "Auto")
    codigo_forcado = _MAPA_IDIOMA_UI.get(idioma_atual) if idioma_atual != "Auto" else None

    sugestao = st.session_state.pop("_sugestao", None)

    if submissao:
        texto = submissao.text or ""
        arquivos = submissao.files or []
        pedido_anexo = st.session_state.pop("_pedido_com_anexo", None)
        if pedido_anexo and not texto.strip():
            # Só usa o pedido se veio o tipo de arquivo prometido: "descreva a
            # imagem" junto com um PDF confundiria o modelo.
            extensoes = EXTENSOES_IMG if pedido_anexo["tipo"] == "imagem" else EXTENSOES_DOC
            if any(f.name.rsplit(".", 1)[-1].lower() in extensoes for f in arquivos):
                texto = pedido_anexo["pedido"]
        imagens_b64 = []
        documentos_indexados = False

        for f in arquivos:
            ext = f.name.rsplit(".", 1)[-1].lower()
            if ext in EXTENSOES_IMG:
                b64 = processar_imagem_otimizada(f)
                if b64:
                    imagens_b64.append(b64)
                else:
                    avisar(f"Não consegui abrir a imagem {f.name}.")
            elif ext in EXTENSOES_DOC:
                _processar_upload_documento(f)
                documentos_indexados = True

        if texto or imagens_b64:
            st.session_state.mensagens.append({"role": "user", "content": texto, "imagens_b64": imagens_b64})
            st.session_state.ultima_foi_voz = False
            st.session_state._pendente_processar = True
            st.rerun()
        elif documentos_indexados:
            st.rerun()

    if sugestao:
        st.session_state.mensagens.append({"role": "user", "content": sugestao, "imagens_b64": []})
        st.session_state.ultima_foi_voz = False
        st.session_state._pendente_processar = True
        st.rerun()

    # --- Áudio pendente de processamento (evita ver o estado "gravado") ---
    # Fluxo: usuário para de gravar → audio != None → salvamos os bytes,
    # incrementamos _mic_version (que troca a key do widget) e damos rerun.
    # No próximo render, o widget já está IDLE (sem player/waveform) e
    # processamos a transcrição aqui, em paz.
    pending = st.session_state.pop("_pending_audio", None)
    if pending:
        texto_voz, _ = transcrever_audio(pending["bytes"], codigo_forcado=pending["lang"])
        if texto_voz:
            st.session_state.mensagens.append({"role": "user", "content": texto_voz, "imagens_b64": []})
            st.session_state.ultima_foi_voz = True
            st.session_state._pendente_processar = True
            st.rerun()
        elif pending["lang"]:
            avisar(
                f"Não entendi o áudio em {pending['lang'].upper()}. Tente de novo, ou volte o idioma para Auto.", "🎙️"
            )
        else:
            avisar("Não entendi o áudio. Tente falar de novo, mais perto do microfone.", "🎙️")

    if audio:
        st.session_state._pending_audio = {
            "bytes": audio.getvalue(),
            "lang": codigo_forcado,
        }
        st.session_state._mic_version = st.session_state.get("_mic_version", 0) + 1
        st.rerun()


# =============================================================================
# Mensagens anteriores
# =============================================================================
@st.cache_data(max_entries=200, show_spinner=False)
def _decodificar_imagem(b64: str) -> bytes:
    return base64.b64decode(b64)


def renderizar_mensagens_anteriores():
    for m in st.session_state.mensagens:
        with st.chat_message(m["role"]):
            imagens = imagens_da_mensagem(m)
            if imagens:
                # st.image serve a imagem por URL (o navegador guarda em
                # cache). Antes o base64 inteiro ia dentro do HTML de novo a
                # cada interação, deixando conversas com fotos lentas.
                st.image([_decodificar_imagem(b64) for b64 in imagens], width=240)

            if m["role"] == "assistant":
                renderizar_resposta_formatada(m["content"])
            else:
                st.markdown(m["content"])

            audio = caminho_audio(m.get("audio"))
            if audio:
                st.audio(audio, format="audio/mp3")
