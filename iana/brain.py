"""
Módulo Lógico e Cognitivo (RAG, Agente de Pesquisa e Comunicação com Ollama).
"""

import hashlib
import json
import logging
import os
import re
import threading
from datetime import datetime

import chromadb
import requests
import streamlit as st
from chromadb.utils import embedding_functions
from requests.adapters import HTTPAdapter

from iana.config import (
    DIRETORIO_MEMORIA,
    MODELO_EMBEDDING,
    MODELO_TEXTO,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_CTX,
    OLLAMA_THINK,
    RAG_DISTANCIA_MAX,
    URL_OLLAMA,
    URL_OLLAMA_CHAT,
)
from iana.storage import avisar

logger = logging.getLogger(__name__)

# Sessão HTTP no nível do módulo (e não em st.cache_resource) para poder ser
# usada também pelas threads em segundo plano (resumo, decisão de pesquisa),
# que não têm o contexto do Streamlit.
_SESSAO_HTTP = requests.Session()
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
_SESSAO_HTTP.mount("http://", _adapter)
_SESSAO_HTTP.mount("https://", _adapter)


class _EmbeddingOllama(embedding_functions.OllamaEmbeddingFunction):
    """Igual ao do chromadb, mas mantém o bge-m3 carregado pelo mesmo tempo
    que o modelo de conversa. Sem keep_alive o Ollama o descarregava após
    5 minutos e a pergunta seguinte esperava o modelo recarregar."""

    def __call__(self, input):
        import numpy as np

        resposta = self._client.embed(model=self.model_name, input=input, keep_alive=OLLAMA_KEEP_ALIVE)
        return [np.array(e, dtype=np.float32) for e in resposta["embeddings"]]


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
    except Exception as e:  # coleção antiga não existe: nada a migrar
        logger.debug("Sem coleção legada para migrar: %s", e)
        dados = {"ids": []}
    if dados["ids"]:
        logger.info("Migrando %d trechos da memória para %s", len(dados["ids"]), colecao.name)
        for i in range(0, len(dados["ids"]), 50):
            colecao.upsert(
                ids=dados["ids"][i : i + 50],
                documents=dados["documents"][i : i + 50],
                metadatas=dados["metadatas"][i : i + 50],
            )
    with open(_marca_migracao(), "w", encoding="utf-8") as f:
        f.write("ok\n")


@st.cache_resource
def obter_colecao_memoria():
    os.makedirs(DIRETORIO_MEMORIA, exist_ok=True)
    cliente = chromadb.PersistentClient(path=DIRETORIO_MEMORIA)
    colecao = cliente.get_or_create_collection(
        name=_nome_colecao(), embedding_function=_EmbeddingOllama(url=URL_OLLAMA, model_name=MODELO_EMBEDDING)
    )
    if _nome_colecao() != COLECAO_LEGADA and not os.path.exists(_marca_migracao()):
        _migrar_colecao_legada(cliente, colecao)
    return colecao


def _dividir_em_trechos(texto: str, tamanho: int = 1000, sobreposicao: int = 200) -> list[str]:
    """Divide em trechos de até `tamanho` caracteres respeitando parágrafos e
    frases. O corte fixo a cada 800 caracteres partia palavras e frases ao
    meio, o que piorava a busca e deixava trechos sem sentido no contexto."""
    pecas: list[str] = []
    for paragrafo in re.split(r"\n\s*\n", texto):
        paragrafo = paragrafo.strip()
        if not paragrafo:
            continue
        if len(paragrafo) <= tamanho:
            pecas.append(paragrafo)
            continue
        for frase in re.split(r"(?<=[.!?;])\s+|\n", paragrafo):
            frase = frase.strip()
            while len(frase) > tamanho:
                corte = frase.rfind(" ", 0, tamanho)
                corte = corte if corte > tamanho // 2 else tamanho
                pecas.append(frase[:corte])
                frase = frase[corte:].strip()
            if frase:
                pecas.append(frase)

    trechos: list[str] = []
    atual: list[str] = []
    for peca in pecas:
        if atual and len("\n".join([*atual, peca])) > tamanho:
            trechos.append("\n".join(atual))
            # Repete o fim do trecho anterior no começo do próximo, para que
            # uma informação na fronteira não fique sem contexto.
            cauda: list[str] = []
            for anterior in reversed(atual):
                if len("\n".join([anterior, *cauda])) > sobreposicao:
                    break
                cauda.insert(0, anterior)
            atual = cauda
        atual.append(peca)
    if atual:
        trechos.append("\n".join(atual))
    return trechos


def adicionar_a_memoria(texto: str, origem: str) -> None:
    if not texto or not texto.strip():
        return
    colecao = obter_colecao_memoria()
    # dict.fromkeys tira trechos repetidos: upsert recusa IDs iguais na mesma chamada.
    chunks = list(dict.fromkeys(_dividir_em_trechos(texto)))
    if not chunks:
        return
    # ID derivado do conteúdo; upsert em vez de add porque add() recusa
    # IDs duplicados (trechos repetidos dentro do mesmo arquivo).
    ids = [f"{origem}_{hashlib.md5(c.encode('utf-8')).hexdigest()[:12]}" for c in chunks]
    anteriores = set(colecao.get(where={"origem": origem}, include=[])["ids"])
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i in range(0, len(chunks), 64):
        colecao.upsert(
            documents=chunks[i : i + 64],
            metadatas=[{"origem": origem, "data": data} for _ in chunks[i : i + 64]],
            ids=ids[i : i + 64],
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
    except Exception as e:  # já não existia
        logger.debug("Coleção legada não removida: %s", e)


# Origens que ficam no índice mas não entram nas respostas. "Imagem" eram
# descrições automáticas de imagens antigas: apareciam em perguntas sem
# relação e confundiam o modelo (ex.: inventar uma imagem a mais).
ORIGENS_IGNORADAS = ["Imagem"]


def buscar_na_memoria(pergunta: str, excluir_origem: str | None = None, consulta_extra: str | None = None) -> str:
    """Trechos relevantes para a pergunta. `consulta_extra` (ex.: a pergunta
    anterior junto com a atual) é buscada na mesma chamada; vale o trecho
    mais próximo de qualquer uma das duas."""
    try:
        colecao = obter_colecao_memoria()
        if colecao.count() == 0:
            return ""
        excluir = ORIGENS_IGNORADAS + ([excluir_origem] if excluir_origem else [])
        filtro = {"origem": {"$nin": excluir}}
        consultas = [pergunta] + ([consulta_extra] if consulta_extra else [])
        resultados = colecao.query(
            query_texts=consultas,
            n_results=4,
            where=filtro,
            include=["documents", "distances"],
        )
        melhores: dict[str, float] = {}
        for docs, dists in zip(resultados["documents"], resultados["distances"], strict=False):
            for d, dist in zip(docs, dists, strict=False):
                if d not in melhores or dist < melhores[d]:
                    melhores[d] = dist
        # Sem o limite, os 4 trechos mais próximos entravam sempre, mesmo
        # sem relação nenhuma com a pergunta.
        documentos = [d for d, dist in sorted(melhores.items(), key=lambda x: x[1]) if dist <= RAG_DISTANCIA_MAX][:4]
        # Sucesso: libera o aviso para que uma futura falha volte a notificar.
        st.session_state["_memoria_erro_avisado"] = False
        if not documentos:
            return ""
        return "\n\n---\n\n".join(documentos)
    except Exception as e:
        logger.warning("Falha ao consultar a memoria vetorial: %s", e, exc_info=True)
        if not st.session_state.get("_memoria_erro_avisado"):
            st.session_state["_memoria_erro_avisado"] = True
            avisar("Memória indisponível. A conversa continua, mas sem consultar os documentos memorizados.")
        return ""


def definir_consulta_web(pergunta: str, contexto: list[dict], data_hoje: str) -> str | None:
    """Decide se a pergunta precisa da internet e, se precisar, devolve a
    consulta de busca. Antes o modelo só dizia SIM/NAO e a busca usava a
    pergunta crua, sem contexto: "e o euro?" depois de perguntar do dólar
    virava uma busca por "e o euro?". Não usa st.* (roda em outra thread)."""
    recentes = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in contexto[-4:] if m.get("content"))
    payload = {
        "model": MODELO_TEXTO,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"Hoje é {data_hoje}. Decida se a ÚLTIMA pergunta do usuário precisa de informação atual "
                    "da internet: notícias, eventos recentes, resultados esportivos, cotações e preços, clima, "
                    "lançamentos, pessoas ou empresas em evidência, ou qualquer fato que possa ter mudado "
                    "recentemente. Conhecimento geral, explicações, programação, textos criativos, conversa e "
                    "perguntas sobre documentos ou imagens enviados NÃO precisam.\n"
                    'Responda em JSON: {"precisa": true ou false, "consulta": "..."}. Se precisar, "consulta" '
                    "é a busca a fazer: curta, só palavras-chave, com o contexto da conversa necessário para "
                    'fazer sentido sozinha (ex.: "cotação euro hoje"). Se não precisar, deixe "consulta" vazia.'
                ),
            },
            {
                "role": "user",
                "content": (
                    (f"Conversa recente:\n{recentes}\n\n" if recentes else "") + f"Última pergunta: {pergunta}"
                ),
            },
        ],
        # Saída estruturada: em texto livre o modelo respondia coisas como
        # "Precisa de informação atual da internet: sim", que viravam a busca.
        "format": {
            "type": "object",
            "properties": {"precisa": {"type": "boolean"}, "consulta": {"type": "string"}},
            "required": ["precisa", "consulta"],
        },
        "stream": False,
        "think": OLLAMA_THINK,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": OLLAMA_NUM_CTX, "temperature": 0.0, "num_predict": 60},
    }
    try:
        res = _SESSAO_HTTP.post(URL_OLLAMA_CHAT, json=payload, timeout=30)
        if res.status_code != 200:
            return None
        decisao = json.loads(res.json().get("message", {}).get("content", "") or "{}")
    except Exception as e:
        logger.warning("Falha ao decidir a pesquisa web: %s", e, exc_info=True)
        return None
    if not isinstance(decisao, dict) or decisao.get("precisa") is not True:
        return None
    consulta = str(decisao.get("consulta") or "").strip()
    return (consulta or pergunta)[:200]


def buscar_na_web(query: str) -> str:
    try:
        from ddgs import DDGS

        resultados = list(DDGS().text(query, region="br-pt", max_results=5))
        return (
            "\n".join(f"- {r.get('title', '')}: {r.get('body', '')} ({r.get('href', '')})" for r in resultados)
            if resultados
            else ""
        )
    except Exception as e:
        logger.warning("Falha na busca web (%s): %s", query, e, exc_info=True)
        return ""


def atualizar_resumo_trabalho(mensagens: list[dict], resumo_atual: str) -> str:
    """Não usa st.*: roda em segundo plano, depois da resposta."""
    historico = "\n".join([f"{m['role']}: {m['content']}" for m in mensagens[-8:]])
    payload = {
        "model": MODELO_TEXTO,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você mantém o resumo de uma conversa. Atualize o resumo anterior com as mensagens novas, "
                    "de forma concisa, preservando fatos, nomes, números, preferências e decisões importantes. "
                    "Responda apenas com o resumo."
                ),
            },
            {
                "role": "user",
                "content": f"Resumo anterior: {resumo_atual or '(nenhum)'}\n\nMensagens novas:\n{historico}",
            },
        ],
        "stream": False,
        "think": OLLAMA_THINK,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": OLLAMA_NUM_CTX, "temperature": 0.2, "num_predict": 300},
    }
    try:
        res = _SESSAO_HTTP.post(URL_OLLAMA_CHAT, json=payload, timeout=120)
        if res.status_code == 200:
            # Resposta vazia não pode apagar o resumo que já existia.
            novo = res.json().get("message", {}).get("content", "").strip()
            return novo or resumo_atual
    except Exception as e:
        logger.warning("Falha ao atualizar resumo: %s", e, exc_info=True)
    return resumo_atual


def _aquecer(modelo: str, embedding: bool = False) -> None:
    try:
        if embedding:
            _SESSAO_HTTP.post(
                URL_OLLAMA + "/api/embed",
                json={"model": modelo, "input": ["."], "keep_alive": OLLAMA_KEEP_ALIVE},
                timeout=300,
            )
        else:
            # Mensagens vazias só carregam o modelo, com o mesmo num_ctx das
            # conversas (outro valor faria o Ollama recarregar depois).
            _SESSAO_HTTP.post(
                URL_OLLAMA_CHAT,
                json={
                    "model": modelo,
                    "messages": [],
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {"num_ctx": OLLAMA_NUM_CTX},
                },
                timeout=300,
            )
    except Exception as e:
        logger.info("Não foi possível pré-carregar %s: %s", modelo, e)


@st.cache_resource(show_spinner=False)
def aquecer_modelos() -> bool:
    """Carrega o modelo de conversa e o de embeddings em segundo plano assim
    que o app abre. Do disco, o gemma4 levou ~45 s para carregar, e esse
    tempo caía todo na primeira pergunta. Roda uma vez por processo."""
    for modelo, emb in ((MODELO_TEXTO, False), (MODELO_EMBEDDING, True)):
        threading.Thread(target=_aquecer, args=(modelo, emb), daemon=True).start()
    return True


def gerar_streaming_ollama(payload: dict):
    sessao = _SESSAO_HTTP

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
        yield (f"⚠️ Ollama retornou HTTP {res.status_code}.\n\nResposta: `{corpo or '(vazia)'}`")
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
            if "error" in dados:
                yield f"\n\n⚠️ Erro do Ollama: `{dados['error']}`"
                return
            if "message" in dados:
                yield dados["message"].get("content", "")
            if dados.get("done") and dados.get("done_reason") == "length":
                yield "\n\n*(resposta interrompida pelo limite de tamanho; peça para continuar)*"
    except requests.RequestException as e:
        logger.error("Streaming do Ollama interrompido: %s", e, exc_info=True)
        yield f"\n\n⚠️ Conexão interrompida durante a resposta: `{type(e).__name__}: {e}`"
    finally:
        # Se o Streamlit interromper a geração (nova mensagem, troca de
        # conversa), fecha a conexão para o Ollama parar de gerar à toa.
        res.close()
