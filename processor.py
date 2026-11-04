"""
Módulo de Processamento de Respostas e Orquestração do Fluxo de Chat.
"""
import os
import time
import uuid
import base64
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

from config import (
    SYSTEM_PROMPT, MODELO_TEXTO, MODELO_VISAO, OLLAMA_KEEP_ALIVE, OLLAMA_OPTIONS, OLLAMA_OPTIONS_VISAO,
    OLLAMA_THINK, PROMPT_PADRAO_IMAGEM, COMPLEMENTO_PROMPT_VISAO,
    HISTORICO_MAX_MENSAGENS, HISTORICO_MAX_CHARS, HISTORICO_MAX_MENSAGENS_VISAO,
)
from storage import salvar_conversa, gerar_titulo_automatico, imagens_da_mensagem
from media import gerar_audio_resposta, renderizar_audio_sequencial
from brain import (
    buscar_na_memoria, definir_consulta_web, buscar_na_web, atualizar_resumo_trabalho, gerar_streaming_ollama
)

logger = logging.getLogger(__name__)

# Limite do documento ativo enviado inteiro ao modelo (~7 mil tokens), para
# caber no num_ctx junto com histórico, resumo e resposta. Acima disso,
# manda-se o início e o RAG cobre o resto.
MAX_CHARS_DOCUMENTO = 24000

# Resumo a cada N mensagens novas.
INTERVALO_RESUMO = 6

# Tarefas em segundo plano (decisão de pesquisa web, resumo). Nenhuma delas
# usa st.*: threads sem o contexto do Streamlit não podem mexer na sessão.
_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="iana")

_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]

def _data_hoje() -> str:
    # Só a data, sem a hora: o prompt do sistema fica igual o dia todo e o
    # Ollama reaproveita o processamento dele de uma pergunta para outra.
    agora = datetime.now()
    return f"{_DIAS[agora.weekday()]}, {agora.day} de {_MESES[agora.month - 1]} de {agora.year}"

def _mensagem_valida(m: dict) -> bool:
    """Respostas de erro e vazias não voltam para o modelo como se fossem
    respostas de verdade."""
    conteudo = m.get("content") or ""
    if m["role"] == "assistant" and (conteudo.startswith("⚠️") or conteudo.startswith("Erro:") or conteudo == "(sem resposta)"):
        return False
    return bool(conteudo.strip() or imagens_da_mensagem(m))

def _montar_historico(anteriores: list[dict], tem_img: bool) -> list[dict]:
    """Últimas mensagens dentro de um limite de mensagens e de caracteres.
    Imagens antigas só vão para o modelo de visão: o gemma4 recebia as
    imagens do histórico em toda pergunta de texto e as descrevia errado."""
    limite = HISTORICO_MAX_MENSAGENS_VISAO if tem_img else HISTORICO_MAX_MENSAGENS
    selecionadas: list[dict] = []
    total = 0
    for m in reversed(anteriores[-limite:]):
        if not _mensagem_valida(m):
            continue
        conteudo = m.get("content") or ""
        imagens = imagens_da_mensagem(m)
        if imagens and not tem_img:
            n = len(imagens)
            conteudo = f"[{n} imagem{'ns' if n > 1 else ''} enviada{'s' if n > 1 else ''}]\n{conteudo}".strip()
        total += len(conteudo)
        if total > HISTORICO_MAX_CHARS and selecionadas:
            break
        item = {"role": m["role"], "content": conteudo}
        if imagens and tem_img:
            item["images"] = imagens
        selecionadas.append(item)
    selecionadas.reverse()
    while selecionadas and selecionadas[0]["role"] != "user":
        selecionadas.pop(0)
    return selecionadas

def _pesquisar(pergunta: str, contexto: list[dict], data_hoje: str) -> tuple[str | None, str]:
    consulta = definir_consulta_web(pergunta, contexto, data_hoje)
    return consulta, (buscar_na_web(consulta) if consulta else "")

def _aplicar_resumo_pronto() -> None:
    pendente = st.session_state.get("_resumo_futuro")
    if not pendente or not pendente[1].done():
        return
    st.session_state._resumo_futuro = None
    id_conversa, futuro = pendente
    if id_conversa != st.session_state.id_conversa_atual:
        return
    try:
        st.session_state.resumo_conversa = futuro.result()
    except Exception as e:
        logger.warning("Falha no resumo em segundo plano: %s", e)

def _agendar_resumo() -> None:
    """O resumo era feito ANTES da resposta, a cada 6 mensagens: uma chamada
    extra ao modelo (até 300 tokens) que atrasava a resposta em vários
    segundos. Agora roda em segundo plano depois dela e entra na próxima."""
    mensagens = st.session_state.mensagens
    if len(mensagens) - st.session_state.get("_ultimo_resumo_em", 0) < INTERVALO_RESUMO:
        return
    if st.session_state.get("_resumo_futuro"):
        return
    copia = [{"role": m["role"], "content": m.get("content") or ""} for m in mensagens if _mensagem_valida(m)]
    futuro = _EXECUTOR.submit(atualizar_resumo_trabalho, copia, st.session_state.resumo_conversa)
    st.session_state._resumo_futuro = (st.session_state.id_conversa_atual, futuro)
    st.session_state._ultimo_resumo_em = len(mensagens)

def processar_resposta(estado: dict, modo_voz: bool = False) -> None:
    ultima = st.session_state.mensagens[-1]
    anteriores = st.session_state.mensagens[:-1]
    imagens = imagens_da_mensagem(ultima)
    tem_img = bool(imagens)
    pergunta = ultima["content"]

    texto_acumulado = ""
    caminho_final = ""

    try:
        _aplicar_resumo_pronto()
        data_hoje = _data_hoje()

        # A pesquisa web (decisão + busca) começa já, em paralelo com a
        # memória e o resto do preparo. Antes tudo rodava em sequência.
        futuro_web = None
        if not tem_img and estado.get("pesquisa_web") and pergunta.strip():
            contexto = [{"role": m["role"], "content": m.get("content") or ""} for m in anteriores[-4:]]
            futuro_web = _EXECUTOR.submit(_pesquisar, pergunta, contexto, data_hoje)

        # Ordem pensada para o cache do Ollama: o que muda pouco (sistema,
        # documento, resumo, histórico) vem primeiro e o que muda a cada
        # pergunta (memória, web) vai na última mensagem. Assim o Ollama
        # reaproveita o processamento do início e responde mais rápido.
        prompt_sistema = f"{SYSTEM_PROMPT}\nHoje é {data_hoje}.\n" + (COMPLEMENTO_PROMPT_VISAO if tem_img else "")
        mensagens_api = [{"role": "system", "content": prompt_sistema}]

        with st.chat_message("assistant"):
            # Placeholder que aparece como "..." durante o preparo e vira o
            # texto em streaming assim que o primeiro token chega.
            placeholder = st.empty()
            placeholder.markdown("...")

            doc = st.session_state.get("documento_ativo")
            # Com imagem, o documento fica de fora pelo mesmo motivo do RAG
            # abaixo: texto longo no contexto confundia o modelo de visão.
            if doc and doc.get("texto") and not tem_img:
                texto_doc = doc["texto"]
                if len(texto_doc) > MAX_CHARS_DOCUMENTO:
                    texto_doc = (
                        texto_doc[:MAX_CHARS_DOCUMENTO]
                        + "\n\n[... documento truncado; trechos relevantes do restante podem aparecer na memória ...]"
                    )
                mensagens_api.append({
                    "role": "system",
                    "content": f"Documento anexado pelo usuário ({doc['nome']}):\n\n{texto_doc}"
                })

            if st.session_state.resumo_conversa:
                mensagens_api.append({
                    "role": "system",
                    "content": f"Resumo da conversa até aqui: {st.session_state.resumo_conversa}"
                })

            mensagens_api.extend(_montar_historico(anteriores, tem_img))

            contexto_extra = []
            # Com imagem, o RAG fica de fora: os trechos no contexto faziam o
            # modelo de visão contar imagens que não existem.
            if pergunta.strip() and not tem_img:
                # Se o documento coube inteiro, não repete os trechos dele vindos do RAG.
                excluir = doc["nome"] if doc and len(doc.get("texto", "")) <= MAX_CHARS_DOCUMENTO else None
                # Perguntas curtas costumam depender da anterior ("e o segundo
                # item?"): busca também com a pergunta anterior junto.
                anterior_usuario = next(
                    (m.get("content") for m in reversed(anteriores) if m["role"] == "user" and m.get("content")), ""
                )
                extra = f"{anterior_usuario[:300]} {pergunta}" if anterior_usuario and len(pergunta) < 80 else None
                memoria = buscar_na_memoria(pergunta, excluir_origem=excluir, consulta_extra=extra)
                if memoria:
                    contexto_extra.append(f"Trechos da memória (documentos do usuário):\n{memoria}")

            if futuro_web:
                try:
                    consulta, web = futuro_web.result(timeout=60)
                except Exception as e:
                    logger.warning("Pesquisa web falhou: %s", e)
                    consulta, web = None, ""
                if web:
                    contexto_extra.append(f"Resultados da web para \"{consulta}\" (hoje é {data_hoje}):\n{web}")

            pergunta_efetiva = pergunta if pergunta.strip() else (PROMPT_PADRAO_IMAGEM if tem_img else "")
            if contexto_extra:
                # Sem o aviso o modelo achava que o usuário tinha colado os
                # resultados ("os resultados que você me mostrou...").
                pergunta_efetiva = (
                    "[Informações buscadas automaticamente pela iAna para ajudar na resposta. "
                    "O usuário não as escreveu nem as vê.]\n\n"
                    + "\n\n".join(contexto_extra)
                    + f"\n\n[Mensagem do usuário]\n{pergunta_efetiva}"
                )

            msg_final = {"role": "user", "content": pergunta_efetiva}
            if tem_img:
                msg_final["images"] = imagens
            mensagens_api.append(msg_final)

            # --- Streaming ---
            payload = {
                "model": MODELO_VISAO if tem_img else MODELO_TEXTO,
                "messages": mensagens_api,
                "stream": True,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": OLLAMA_OPTIONS_VISAO if tem_img else OLLAMA_OPTIONS,
            }
            if not tem_img:
                payload["think"] = OLLAMA_THINK

            # Redesenhar o markdown inteiro a cada token custava O(n²) e
            # travava a página em respostas longas; agora ~12 vezes por segundo.
            ultimo_desenho = 0.0
            for token in gerar_streaming_ollama(payload):
                texto_acumulado += token
                agora = time.monotonic()
                if agora - ultimo_desenho >= 0.08:
                    placeholder.markdown(texto_acumulado + " ▌")
                    ultimo_desenho = agora
            placeholder.markdown(texto_acumulado or "...")

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
            # O nome fica na sessão: antes o arquivo inteiro da conversa (com
            # as imagens) era relido do disco a cada resposta só para isso.
            nome = st.session_state.get("nome_conversa") or gerar_titulo_automatico(pergunta)
            st.session_state.nome_conversa = nome
            salvar_conversa(
                st.session_state.id_conversa_atual,
                st.session_state.mensagens,
                nome,
                st.session_state.projeto_atual,
                st.session_state.resumo_conversa
            )
        except Exception as e:
            logger.warning("Falha ao salvar conversa: %s", e, exc_info=True)

        try:
            _agendar_resumo()
        except Exception as e:
            logger.warning("Falha ao agendar resumo: %s", e, exc_info=True)
