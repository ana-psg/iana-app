"""
Módulo de Gestão de Persistência (Projetos, Conversas e Estado).
"""

import json
import os
import re
import time
import uuid
from datetime import datetime

import streamlit as st

from iana.config import DIRETORIO_AUDIO, DIRETORIO_HISTORICO, TAMANHO_MAX_TITULO


def criar_nova_sessao(projeto: str = "Geral") -> None:
    st.session_state.id_conversa_atual = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:4]
    st.session_state.mensagens = []
    st.session_state.resumo_conversa = ""
    st.session_state.nome_conversa = None
    st.session_state.projeto_atual = projeto
    st.session_state.ultima_foi_voz = False
    st.session_state.anexo_pendente = None
    st.session_state.documento_ativo = None
    st.session_state._anexo_ja_processado = None
    st.session_state._uploader_version = st.session_state.get("_uploader_version", 0) + 1
    st.session_state._pendente_processar = False
    st.session_state._doc_uploader_version = st.session_state.get("_doc_uploader_version", 0) + 1
    st.session_state._mic_version = st.session_state.get("_mic_version", 0) + 1
    st.session_state._ultimo_resumo_em = 0
    st.session_state._pedido_com_anexo = None
    st.session_state._resumo_futuro = None


def avisar(texto: str, icone: str = "⚠️", duracao: str = "long") -> None:
    """Agenda um aviso (toast) para o fim do ciclo. Um st.toast chamado
    direto some quando o app recarrega logo em seguida (st.rerun), o que
    acontece depois de quase toda ação: os avisos nunca apareciam."""
    st.session_state.setdefault("_avisos", []).append((texto, icone, duracao))


def exibir_avisos_pendentes() -> None:
    for texto, icone, duracao in st.session_state.pop("_avisos", []):
        st.toast(texto, icon=icone, duration=duracao)


def garantir_estado_inicial() -> None:
    if "projeto_atual" not in st.session_state:
        st.session_state.projeto_atual = "Geral"
    if "id_conversa_atual" not in st.session_state:
        criar_nova_sessao(st.session_state.projeto_atual)

    chaves = {
        "resumo_conversa": "",
        "nome_conversa": None,
        "_resumo_futuro": None,
        "ultima_foi_voz": False,
        "anexo_pendente": None,
        "documento_ativo": None,
        "_anexo_ja_processado": None,
        "_uploader_version": 0,
        "_pendente_processar": False,
        "_doc_uploader_version": 0,
        "_mic_version": 0,
        "_ultimo_resumo_em": 0,
        "_memoria_erro_avisado": False,
    }
    for chave, valor in chaves.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _caminho_conversa(id_conversa: str) -> str:
    id_seguro = re.sub(r"[^a-zA-Z0-9_\-]", "", id_conversa)
    if not id_seguro:
        raise ValueError(f"id_conversa invalido: {id_conversa!r}")
    base = os.path.realpath(DIRETORIO_HISTORICO)
    alvo = os.path.realpath(os.path.join(base, f"{id_seguro}.json"))
    if os.path.commonpath([base, alvo]) != base:
        raise ValueError(f"Caminho fora do diretorio de historico: {id_conversa!r}")
    return alvo


def listar_conversas() -> list[str]:
    if not os.path.exists(DIRETORIO_HISTORICO):
        return []
    return sorted(
        (f.replace(".json", "") for f in os.listdir(DIRETORIO_HISTORICO) if f.endswith(".json")), reverse=True
    )


@st.cache_data(ttl=3, show_spinner=False)
def listar_conversas_cached() -> list[str]:
    return listar_conversas()


@st.cache_data(max_entries=2000, show_spinner=False)
def _ler_metadados(caminho: str, mtime: float) -> dict:
    # mtime entra na chave do cache: o arquivo só é relido quando muda.
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, dict):
        dados = {"mensagens": dados}
    return {
        "nome": dados.get("nome"),
        "projeto": dados.get("projeto", "Geral"),
        "mensagens": bool(dados.get("mensagens")),
    }


def carregar_metadados_conversas(conversas: list[str]) -> dict[str, dict]:
    """Nome, projeto e se há mensagens de cada conversa, sem manter o conteúdo
    (mensagens e imagens) em memória. Para a sidebar, que roda a cada interação."""
    metadados = {}
    for c_id in conversas:
        try:
            caminho = _caminho_conversa(c_id)
            metadados[c_id] = _ler_metadados(caminho, os.path.getmtime(caminho))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return metadados


def salvar_conversa(
    id_conversa: str, mensagens: list[dict], nome: str | None = None, projeto: str = "Geral", resumo: str = ""
) -> None:
    os.makedirs(DIRETORIO_HISTORICO, exist_ok=True)
    caminho_final = _caminho_conversa(id_conversa)
    caminho_tmp = caminho_final + ".tmp"
    with open(caminho_tmp, "w", encoding="utf-8") as f:
        json.dump(
            {"nome": nome, "projeto": projeto, "resumo": resumo, "mensagens": mensagens},
            f,
            ensure_ascii=False,
            indent=4,
        )
    os.replace(caminho_tmp, caminho_final)
    listar_conversas_cached.clear()


def carregar_conversa(id_conversa: str) -> dict:
    caminho = _caminho_conversa(id_conversa)
    if not os.path.exists(caminho):
        return {"nome": None, "projeto": "Geral", "resumo": "", "mensagens": []}
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return dados if isinstance(dados, dict) else {"nome": None, "projeto": "Geral", "resumo": "", "mensagens": dados}


def apagar_todo_historico() -> None:
    """Apaga todas as conversas e os áudios das respostas (que só existem
    para serem reproduzidos dentro delas)."""
    if os.path.exists(DIRETORIO_HISTORICO):
        for f in os.listdir(DIRETORIO_HISTORICO):
            if f.endswith(".json"):
                os.remove(os.path.join(DIRETORIO_HISTORICO, f))
    if os.path.exists(DIRETORIO_AUDIO):
        for f in os.listdir(DIRETORIO_AUDIO):
            if f.endswith(".mp3"):
                os.remove(os.path.join(DIRETORIO_AUDIO, f))
    listar_conversas_cached.clear()


def caminho_audio(referencia: str | None) -> str | None:
    """Caminho do áudio de uma mensagem, sempre dentro da pasta audio/ atual.
    As conversas antigas guardavam o caminho completo, que deixa de valer
    quando a pasta do app é movida ou renomeada; por isso só o nome conta."""
    if not referencia:
        return None
    caminho = os.path.join(DIRETORIO_AUDIO, os.path.basename(referencia))
    return caminho if os.path.exists(caminho) else None


def _audios_referenciados() -> set[str]:
    referenciados = set()
    for c_id in listar_conversas():
        try:
            for m in carregar_conversa(c_id).get("mensagens", []):
                if m.get("audio"):
                    referenciados.add(os.path.basename(m["audio"]).lower())
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return referenciados


def limpar_audios_orfaos(idade_minima_s: int = 3600) -> int:
    """Remove áudios que nenhuma conversa usa mais (ex.: conversa apagada).
    A idade mínima evita apagar o áudio de uma resposta que ainda está
    sendo salva. Retorna quantos arquivos foram removidos."""
    if not os.path.exists(DIRETORIO_AUDIO):
        return 0
    referenciados = _audios_referenciados()
    agora = time.time()
    removidos = 0
    for f in os.listdir(DIRETORIO_AUDIO):
        caminho = os.path.join(DIRETORIO_AUDIO, f)
        if not f.endswith(".mp3") or f.lower() in referenciados:
            continue
        try:
            if agora - os.path.getmtime(caminho) >= idade_minima_s:
                os.remove(caminho)
                removidos += 1
        except OSError:
            continue
    return removidos


def obter_nome_exibicao(dados_conversa: dict, id_conversa: str) -> str:
    if dados_conversa.get("nome"):
        return dados_conversa["nome"]
    if not dados_conversa.get("mensagens"):
        return "Nova conversa"
    try:
        return f"{id_conversa[6:8]}/{id_conversa[4:6]} {id_conversa[9:11]}:{id_conversa[11:13]}"
    except Exception:
        return id_conversa


def imagens_da_mensagem(mensagem: dict) -> list[str]:
    """Imagens (base64) de uma mensagem. Aceita o formato antigo, com uma
    única imagem em 'imagem_b64', e o atual, com a lista 'imagens_b64'."""
    if mensagem.get("imagens_b64"):
        return mensagem["imagens_b64"]
    return [mensagem["imagem_b64"]] if mensagem.get("imagem_b64") else []


def gerar_titulo_automatico(pergunta: str) -> str | None:
    titulo = re.sub(r"\s+", " ", pergunta.strip()).rstrip("?!.,;:")
    if not titulo:
        return None
    return titulo[: TAMANHO_MAX_TITULO - 3].rsplit(" ", 1)[0] + "..." if len(titulo) > TAMANHO_MAX_TITULO else titulo
