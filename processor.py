"""
Módulo de Processamento de Respostas e Orquestração do Fluxo de Chat.
"""
import os
import uuid
import base64
import logging
import streamlit as st

from config import (
    SYSTEM_PROMPT, MODELO_TEXTO, MODELO_VISAO, OLLAMA_KEEP_ALIVE, OLLAMA_OPTIONS, OLLAMA_THINK,
    PROMPT_PADRAO_IMAGEM, COMPLEMENTO_PROMPT_VISAO
)
from storage import carregar_conversa, salvar_conversa, gerar_titulo_automatico, imagens_da_mensagem
from media import gerar_audio_resposta, renderizar_audio_sequencial
from brain import buscar_na_memoria, avaliar_necessidade_pesquisa, buscar_na_web, atualizar_resumo_trabalho, gerar_streaming_ollama

logger = logging.getLogger(__name__)

# Limite do documento ativo enviado inteiro ao modelo (~7 mil tokens), para
# caber no num_ctx junto com histórico, resumo e resposta. Acima disso,
# manda-se o início e o RAG cobre o resto.
MAX_CHARS_DOCUMENTO = 24000

def processar_resposta(estado: dict, modo_voz: bool = False) -> None:
    ultima = st.session_state.mensagens[-1]
    imagens = imagens_da_mensagem(ultima)
    tem_img = bool(imagens)
    pergunta = ultima["content"]

    texto_acumulado = ""
    caminho_final = ""

    try:
        prompt_sistema = SYSTEM_PROMPT + (COMPLEMENTO_PROMPT_VISAO if tem_img else "")
        mensagens_api = [{"role": "system", "content": prompt_sistema}]

        with st.chat_message("assistant"):
            # Placeholder que aparece como "..." durante o preparo e vira o
            # texto em streaming assim que o primeiro token chega.
            placeholder = st.empty()
            placeholder.markdown("...")

            # --- Preparo silencioso: resumo, RAG, histórico, web ---
            ultimo_resumo_em = st.session_state.get("_ultimo_resumo_em", 0)
            if len(st.session_state.mensagens) - ultimo_resumo_em >= 6:
                st.session_state.resumo_conversa = atualizar_resumo_trabalho(
                    st.session_state.mensagens, st.session_state.resumo_conversa
                )
                st.session_state._ultimo_resumo_em = len(st.session_state.mensagens)

            if st.session_state.resumo_conversa:
                mensagens_api.append({
                    "role": "system",
                    "content": f"Contexto prévio: {st.session_state.resumo_conversa}"
                })

            doc = st.session_state.get("documento_ativo")
            # Com imagem, o documento fica de fora pelo mesmo motivo do RAG
            # abaixo: texto longo no contexto confundia o modelo de visão.
            if doc and doc.get("texto") and not tem_img:
                texto_doc = doc["texto"]
                if len(texto_doc) > MAX_CHARS_DOCUMENTO:
                    texto_doc = (
                        texto_doc[:MAX_CHARS_DOCUMENTO]
                        + "\n\n[... documento truncado; trechos relevantes do restante podem aparecer na base de dados ...]"
                    )
                mensagens_api.append({
                    "role": "system",
                    "content": f"Documento anexado pelo usuário ({doc['nome']}):\n\n{texto_doc}"
                })

            # Com imagem, o RAG fica de fora: os trechos numerados [1]..[4]
            # faziam o modelo de visão contar imagens que não existem.
            if pergunta.strip() and not tem_img:
                # Se o documento coube inteiro, não repete os trechos dele vindos do RAG.
                excluir = doc["nome"] if doc and len(doc.get("texto", "")) <= MAX_CHARS_DOCUMENTO else None
                memoria = buscar_na_memoria(pergunta, excluir_origem=excluir)
                if memoria:
                    mensagens_api.append({
                        "role": "system",
                        "content": f"Base de dados: {memoria}"
                    })

            n_historico = 3 if tem_img else 5
            for m in st.session_state.mensagens[-n_historico:-1]:
                item = {"role": m["role"], "content": m["content"]}
                if imagens_da_mensagem(m):
                    item["images"] = imagens_da_mensagem(m)
                mensagens_api.append(item)

            pergunta_efetiva = pergunta if pergunta.strip() else (PROMPT_PADRAO_IMAGEM if tem_img else "")

            msg_final = {"role": ultima["role"], "content": pergunta_efetiva}
            if tem_img:
                msg_final["images"] = imagens

            if not tem_img and estado.get("pesquisa_web") and avaliar_necessidade_pesquisa(pergunta):
                web = buscar_na_web(pergunta)
                if web:
                    msg_final["content"] = f"Dados da web:\n{web}\n\nPergunta: {pergunta}"

            mensagens_api.append(msg_final)

            # --- Streaming ---
            payload = {
                "model": MODELO_VISAO if tem_img else MODELO_TEXTO,
                "messages": mensagens_api,
                "stream": True,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": OLLAMA_OPTIONS,
            }
            if not tem_img:
                payload["think"] = OLLAMA_THINK

            for token in gerar_streaming_ollama(payload):
                texto_acumulado += token
                placeholder.markdown(texto_acumulado)

            if modo_voz:
                caminho_final = gerar_audio_resposta(texto_acumulado, uuid.uuid4().hex[:6])
                if caminho_final:
                    with open(caminho_final, "rb") as f:
                        renderizar_audio_sequencial(base64.b64encode(f.read()).decode())

    except Exception as e:
        logger.error("Erro em processar_resposta: %s", e, exc_info=True)
        texto_acumulado = texto_acumulado or f"Erro: {type(e).__name__}: {e}"
        st.error(texto_acumulado)

    finally:
        st.session_state.mensagens.append({
            "role": "assistant",
            "content": texto_acumulado or "(sem resposta)",
            # Só o nome do arquivo: o caminho completo quebra se a pasta mudar.
            "audio": os.path.basename(caminho_final) if caminho_final else ""
        })

        try:
            nome_atual = carregar_conversa(st.session_state.id_conversa_atual).get("nome")
            nome_convers = nome_atual or gerar_titulo_automatico(pergunta)
            salvar_conversa(
                st.session_state.id_conversa_atual,
                st.session_state.mensagens,
                nome_convers,
                st.session_state.projeto_atual,
                st.session_state.resumo_conversa
            )
        except Exception as e:
            logger.warning("Falha ao salvar conversa: %s", e, exc_info=True)