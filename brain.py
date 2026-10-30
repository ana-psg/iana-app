"""
Módulo Lógico e Cognitivo (RAG, Agente de Pesquisa e Comunicação com Ollama).
"""
import os
import re
import json
import hashlib
import logging
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
import chromadb
from chromadb.utils import embedding_functions
import streamlit as st

from storage import avisar

from config import (
    DIRETORIO_MEMORIA, URL_OLLAMA_CHAT, URL_OLLAMA_EMBED,
    MODELO_TEXTO, MODELO_EMBEDDING, RAG_DISTANCIA_MAX, OLLAMA_KEEP_ALIVE, OLLAMA_THINK, OLLAMA_NUM_CTX
)

logger = logging.getLogger(__name__)

@st.cache_resource
def obter_sessao_http() -> requests.Session:
    sessao = requests.Session()
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
    sessao.mount("http://", adapter)
    sessao.mount("https://", adapter)
    return sessao

# Coleção da versão 1.0/1.1 (embeddings do nomic-embed-text). Fica intacta
# como backup depois da migração.
COLECAO_LEGADA = "iana_memoria"

def _nome_colecao() -> str:
    # Uma coleção por modelo: vetores de modelos diferentes não se misturam
    # (nem têm o mesmo tamanho).
    return "iana_memoria_" + re.sub(r"[^a-zA-Z0-9._-]", "-", MODELO_EMBEDDING)

def _marca_migracao() -> str:
    return os.path.join(DIRETORIO_MEMORIA, f".migrado_{_nome_colecao()}")

def _migrar_colecao_legada(cliente, colecao) -> None:
    """Copia os trechos da coleção antiga para a nova, recalculando os
    vetores com o modelo atual. Roda uma única vez: a marca só é gravada
    no fim, então uma migração interrompida é retomada (upsert não duplica).
    Antes, migrar sempre que a nova estivesse vazia trazia de volta
    documentos que a pessoa já tinha removido."""
    try:
        legada = cliente.get_collection(COLECAO_LEGADA)
        dados = legada.get(include=["documents", "metadatas"])
    except Exception:
        dados = {"ids": []}
    if dados["ids"]:
        logger.info("Migrando %d trechos da memória para %s", len(dados["ids"]), colecao.name)
        for i in range(0, len(dados["ids"]), 50):
            colecao.upsert(
                ids=dados["ids"][i:i + 50],
                documents=dados["documents"][i:i + 50],
                metadatas=dados["metadatas"][i:i + 50],
            )
    with open(_marca_migracao(), "w", encoding="utf-8") as f:
        f.write("ok\n")

@st.cache_resource
def obter_colecao_memoria():
    os.makedirs(DIRETORIO_MEMORIA, exist_ok=True)
    cliente = chromadb.PersistentClient(path=DIRETORIO_MEMORIA)
    colecao = cliente.get_or_create_collection(
        name=_nome_colecao(),
        embedding_function=embedding_functions.OllamaEmbeddingFunction(url=URL_OLLAMA_EMBED, model_name=MODELO_EMBEDDING)
    )
    if _nome_colecao() != COLECAO_LEGADA and not os.path.exists(_marca_migracao()):
        _migrar_colecao_legada(cliente, colecao)
    return colecao

def adicionar_a_memoria(texto: str, origem: str) -> None:
    if not texto or not texto.strip():
        return
    colecao = obter_colecao_memoria()
    chunks = [texto[i:i + 1000] for i in range(0, len(texto), 800)]
    if not chunks:
        return
    # ID derivado do conteúdo; upsert em vez de add porque add() recusa
    # IDs duplicados (trechos repetidos dentro do mesmo arquivo).
    ids = [f"{origem}_{hashlib.md5(c.encode('utf-8')).hexdigest()[:12]}" for c in chunks]
    anteriores = set(colecao.get(where={"origem": origem}, include=[])["ids"])
    colecao.upsert(
        documents=chunks,
        metadatas=[{"origem": origem, "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")} for _ in chunks],
        ids=ids
    )
    # Uma versão nova do mesmo arquivo substitui a anterior: sem isso os
    # trechos antigos ficavam junto e o modelo podia responder com dados
    # da versão velha. A limpeza vem DEPOIS de gravar a nova, para que uma
    # falha (ex.: Ollama fora do ar) não deixe o documento sem nenhuma versão.
    obsoletos = anteriores - set(ids)
    if obsoletos:
        colecao.delete(ids=list(obsoletos))

def remover_da_memoria(origem: str) -> None:
    """Remove todos os chunks indexados com a origem dada."""
    if not origem:
        return
    try:
        colecao = obter_colecao_memoria()
        colecao.delete(where={"origem": origem})
    except Exception as e:
        logger.warning("Falha ao remover '%s' da memoria: %s", origem, e, exc_info=True)

def apagar_toda_memoria() -> None:
    """Remove todos os trechos indexados (documentos e descrições antigas)."""
    colecao = obter_colecao_memoria()
    ids = colecao.get(include=[])["ids"]
    if ids:
        colecao.delete(ids=ids)
    # Quem pede para apagar a memória espera que o backup antigo vá junto.
    try:
        chromadb.PersistentClient(path=DIRETORIO_MEMORIA).delete_collection(COLECAO_LEGADA)
    except Exception:
        pass

# Origens que ficam no índice mas não entram nas respostas. "Imagem" eram
# descrições automáticas de imagens antigas: apareciam em perguntas sem
# relação e confundiam o modelo (ex.: inventar uma imagem a mais).
ORIGENS_IGNORADAS = ["Imagem"]

def buscar_na_memoria(pergunta: str, excluir_origem: str | None = None) -> str:
    try:
        colecao = obter_colecao_memoria()
        if colecao.count() == 0:
            return ""
        excluir = ORIGENS_IGNORADAS + ([excluir_origem] if excluir_origem else [])
        filtro = {"origem": {"$nin": excluir}}
        resultados = colecao.query(
            query_texts=[pergunta], n_results=4, where=filtro,
            include=["documents", "distances"],
        )
        # Sem o limite, os 4 trechos mais próximos entravam sempre, mesmo
        # sem relação nenhuma com a pergunta.
        documentos = [
            d for d, dist in zip(resultados["documents"][0], resultados["distances"][0])
            if dist <= RAG_DISTANCIA_MAX
        ]
        # Sucesso: libera o aviso para que uma futura falha volte a notificar.
        st.session_state["_memoria_erro_avisado"] = False
        if not documentos:
            return ""
        return "\n\n".join([f"[{i+1}] {d}" for i, d in enumerate(documentos)])
    except Exception as e:
        logger.warning("Falha ao consultar a memoria vetorial: %s", e, exc_info=True)
        if not st.session_state.get("_memoria_erro_avisado"):
            st.session_state["_memoria_erro_avisado"] = True
            avisar("Memória indisponível. A conversa continua, mas sem consultar os documentos memorizados.")
        return ""

def avaliar_necessidade_pesquisa(pergunta: str) -> bool:
    payload = {
        "model": MODELO_TEXTO,
        "messages": [
            {"role": "system", "content": (
                "Decida se a pergunta precisa de informação atual da internet para ser respondida corretamente: "
                "notícias, eventos recentes, resultados esportivos, cotações e preços, clima, lançamentos, "
                "pessoas ou empresas em evidência, ou qualquer fato que possa ter mudado recentemente. "
                "Conhecimento geral, explicações, programação, textos criativos e conversa NÃO precisam. "
                "Responda APENAS 'SIM' ou 'NAO'."
            )},
            {"role": "user", "content": pergunta}
        ],
        "stream": False,
        "think": OLLAMA_THINK,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": OLLAMA_NUM_CTX, "temperature": 0.0, "num_predict": 5}
    }
    try:
        res = obter_sessao_http().post(URL_OLLAMA_CHAT, json=payload, timeout=30)
        if res.status_code == 200:
            conteudo = res.json().get("message", {}).get("content", "").strip().upper()
            return conteudo.startswith("SIM")
    except Exception as e:
        logger.warning("Falha ao avaliar necessidade de pesquisa: %s", e, exc_info=True)
    return False

def buscar_na_web(query: str) -> str:
    try:
        from ddgs import DDGS
        resultados = list(DDGS().text(query, region="br-pt", max_results=3))
        return "\n".join([f"- {r['title']}: {r['body']}" for r in resultados]) if resultados else ""
    except Exception as e:
        logger.warning("Falha na busca web (%s): %s", query, e, exc_info=True)
        return ""

def atualizar_resumo_trabalho(mensagens: list[dict], resumo_atual: str) -> str:
    historico = "\n".join([f"{m['role']}: {m['content']}" for m in mensagens[-8:]])
    payload = {
        "model": MODELO_TEXTO,
        "messages": [{"role": "system", "content": f"Resuma o estado atual desta conversa de forma concisa. Resumo anterior: {resumo_atual}\n\nMensagens:\n{historico}"}],
        "stream": False,
        "think": OLLAMA_THINK,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": OLLAMA_NUM_CTX, "temperature": 0.2, "num_predict": 300}
    }
    try:
        res = obter_sessao_http().post(URL_OLLAMA_CHAT, json=payload, timeout=60)
        if res.status_code == 200:
            # Resposta vazia não pode apagar o resumo que já existia.
            novo = res.json().get("message", {}).get("content", "").strip()
            return novo or resumo_atual
    except Exception as e:
        logger.warning("Falha ao atualizar resumo: %s", e, exc_info=True)
    return resumo_atual

def gerar_streaming_ollama(payload: dict):
    sessao = obter_sessao_http()

    try:
        res = sessao.post(URL_OLLAMA_CHAT, json=payload, stream=True, timeout=300)
    except requests.RequestException as e:
        logger.error("Falha ao conectar ao Ollama (%s): %s", URL_OLLAMA_CHAT, e, exc_info=True)
        yield (
            f"⚠️ Não foi possível conectar ao Ollama em `{URL_OLLAMA_CHAT}`. "
            f"Verifique se o serviço está em execução.\n\n"
            f"Detalhe: `{type(e).__name__}: {e}`"
        )
        return

    if res.status_code != 200:
        corpo = (res.text or "").strip()[:300]
        logger.error("Ollama retornou HTTP %s: %s", res.status_code, corpo)
        yield (
            f"⚠️ Ollama retornou HTTP {res.status_code}.\n\n"
            f"Resposta: `{corpo or '(vazia)'}`"
        )
        return

    try:
        for linha in res.iter_lines():
            if not linha:
                continue
            try:
                dados = json.loads(linha.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("Linha inválida recebida do Ollama: %.120r (%s)", linha, e)
                continue
            if "message" in dados:
                yield dados["message"].get("content", "")
    except requests.RequestException as e:
        logger.error("Streaming do Ollama interrompido: %s", e, exc_info=True)
        yield f"\n\n⚠️ Conexão interrompida durante a resposta: `{type(e).__name__}: {e}`"