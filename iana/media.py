"""
Módulo de Processamento Multimédia (Áudio, Imagem e Documentos).
"""

import asyncio
import base64
import io
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor

import edge_tts
import pypdf
import speech_recognition as sr
import streamlit as st
from langdetect import DetectorFactory, LangDetectException, detect
from PIL import Image, ImageOps

# Sem semente o langdetect é aleatório: o mesmo texto podia ganhar vozes de
# idiomas diferentes de uma vez para outra.
DetectorFactory.seed = 0

from iana.config import DIRETORIO_AUDIO, IDIOMA_PADRAO, LADO_MAX_IMAGEM, MAPA_IDIOMAS  # noqa: E402  (depois de fixar a semente do langdetect)

logger = logging.getLogger(__name__)


# =============================================================================
# Detecção de idioma
# =============================================================================
def _detectar_idioma(texto: str, fallback: str = IDIOMA_PADRAO) -> str:
    if not texto or len(texto.strip()) < 5:
        return fallback
    try:
        codigo = detect(texto)
    except LangDetectException:
        return fallback
    return codigo if codigo in MAPA_IDIOMAS else fallback


def _prefs_idioma(codigo_iso: str) -> dict:
    return MAPA_IDIOMAS.get(codigo_iso, MAPA_IDIOMAS[IDIOMA_PADRAO])


# =============================================================================
# Extração de Documentos
# =============================================================================
def _decodificar(bytes_data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return bytes_data.decode(enc)
        except UnicodeDecodeError:
            continue
    return bytes_data.decode("utf-8", errors="replace")


def _extrair_docx(ficheiro) -> str:
    from docx import Document

    doc = Document(io.BytesIO(ficheiro.getvalue()))
    partes: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]
    for tabela in doc.tables:
        for linha in tabela.rows:
            celulas = [c.text.strip() for c in linha.cells]
            if any(celulas):
                partes.append(" | ".join(celulas))
    return "\n".join(partes)


def extrair_conteudo_documento(ficheiro) -> str | None:
    nome = ficheiro.name or ""
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    try:
        if ext == "pdf":
            return "".join((p.extract_text() or "") + "\n" for p in pypdf.PdfReader(ficheiro).pages)
        if ext in ("txt", "md", "csv"):
            return _decodificar(ficheiro.getvalue())
        if ext == "docx":
            return _extrair_docx(ficheiro)
    except Exception as e:
        logger.warning("Falha ao extrair conteudo de %s: %s", nome, e, exc_info=True)
        return None
    return None


# =============================================================================
# Imagem
# =============================================================================
def processar_imagem_otimizada(ficheiro) -> str | None:
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(ficheiro.getvalue()))).convert("RGB")
        img.thumbnail((LADO_MAX_IMAGEM, LADO_MAX_IMAGEM))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        logger.warning("Falha ao processar imagem: %s", e, exc_info=True)
        return None


# =============================================================================
# Áudio — Speech-to-Text
# =============================================================================
def obter_reconhecedor_stt() -> sr.Recognizer:
    return sr.Recognizer()


# Bônus do idioma padrão no modo automático. Sem ele, português e espanhol
# empatam quando a mesma pessoa fala os dois com o mesmo sotaque. 1.15 não
# bastava: "Qual é a capital da França" perdia para "cuál era capital de
# Francia" (confiança 0,95 contra 0,82).
_BONUS_IDIOMA_PADRAO = 1.3


def _transcrever_forcado(rec: sr.Recognizer, dados, codigo_iso: str) -> tuple[str | None, str]:
    """Modo manual: tenta apenas o idioma escolhido."""
    prefs = MAPA_IDIOMAS.get(codigo_iso)
    locale = prefs.get("stt") if prefs else None
    if not locale:
        return None, IDIOMA_PADRAO
    try:
        texto = rec.recognize_google(dados, language=locale)
        if texto:
            return texto.strip(), codigo_iso
    except sr.UnknownValueError:
        pass
    except sr.RequestError as e:
        logger.warning("Google STT indisponivel (%s): %s", locale, e)
    except Exception as e:
        logger.warning("Erro no STT (%s): %s", locale, e, exc_info=True)
    return None, IDIOMA_PADRAO


# Penalidade quando o texto transcrito não parece estar no idioma testado.
# O Google às vezes devolve confiança alta para transcrições sem sentido
# num idioma errado (ex.: áudio em português -> "Wow Head capital de Friends"
# em es-ES com 0,89).
_PENALIDADE_IDIOMA_DIVERGENTE = 0.5


def _candidato_stt(rec: sr.Recognizer, dados, codigo_iso: str, locale: str) -> tuple[float, str, str] | None:
    try:
        resultado = rec.recognize_google(dados, language=locale, show_all=True)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        logger.warning("Google STT indisponivel (%s): %s", locale, e)
        return None
    except Exception as e:
        logger.warning("Erro no STT (%s): %s", locale, e, exc_info=True)
        return None

    if not resultado or not isinstance(resultado, dict):
        return None
    alternativas = resultado.get("alternative") or []
    if not alternativas:
        return None

    melhor = alternativas[0]
    texto = (melhor.get("transcript") or "").strip()
    if not texto:
        return None

    try:
        confianca = float(melhor.get("confidence", 0.5) or 0.5)
    except (TypeError, ValueError):
        confianca = 0.5

    score = len(texto) * confianca
    if codigo_iso == IDIOMA_PADRAO:
        score *= _BONUS_IDIOMA_PADRAO
    # langdetect só é confiável a partir de algumas palavras.
    if len(texto) >= 10:
        try:
            if detect(texto) != codigo_iso:
                score *= _PENALIDADE_IDIOMA_DIVERGENTE
        except LangDetectException:
            pass
    return score, texto, codigo_iso


# Identificação de idioma com Whisper. As "confianças" do Google gratuito são
# praticamente fixas por idioma, então a heurística abaixo acaba escolhendo o
# texto mais longo — e espanhol virava francês. O Whisper "base" acertou 7/7
# (pt, en, es, fr) em ~0,5 s no processador. Roda na CPU para não disputar a
# placa de vídeo com os modelos do Ollama.
MODELO_WHISPER = "base"
_CONFIANCA_MINIMA_IDIOMA = 0.5


@st.cache_resource(show_spinner=False)
def _obter_modelo_idioma():
    try:
        from faster_whisper import WhisperModel

        return WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    except Exception as e:
        logger.warning("Whisper indisponivel, usando heuristica de idioma: %s", e)
        return None


def _detectar_idioma_audio(dados: sr.AudioData) -> str | None:
    """Idioma falado (entre os de MAPA_IDIOMAS) ou None se não der para saber."""
    modelo = _obter_modelo_idioma()
    if modelo is None:
        return None
    try:
        import numpy as np

        pcm = dados.get_raw_data(convert_rate=16000, convert_width=2)
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        _, _, probabilidades = modelo.detect_language(audio)
    except Exception as e:
        logger.warning("Falha ao detectar idioma do audio: %s", e, exc_info=True)
        return None
    probabilidades = dict(probabilidades)
    melhor = max(MAPA_IDIOMAS, key=lambda c: probabilidades.get(c, 0.0))
    return melhor if probabilidades.get(melhor, 0.0) >= _CONFIANCA_MINIMA_IDIOMA else None


def _transcrever_auto(rec: sr.Recognizer, dados) -> tuple[str | None, str]:
    """
    Modo automático: o Whisper identifica o idioma e o Google transcreve
    uma vez nesse idioma. Sem Whisper (ou em dúvida), cai na heurística.
    """
    idioma = _detectar_idioma_audio(dados)
    if idioma:
        texto, codigo = _transcrever_forcado(rec, dados, idioma)
        if texto:
            return texto, codigo
    return _transcrever_por_heuristica(rec, dados)


def _transcrever_por_heuristica(rec: sr.Recognizer, dados) -> tuple[str | None, str]:
    """
    Testa todos os idiomas (em paralelo) e escolhe pelo score
        score = len(transcrição) × confiança × (bônus se idioma padrão)
                × (penalidade se o texto não parece do idioma testado)
    Motivo: quando o locale do Google não bate com o áudio, a transcrição
    costuma sair mais curta, com confiança menor ou em outra língua.
    """
    tarefas = [(codigo_iso, prefs["stt"]) for codigo_iso, prefs in MAPA_IDIOMAS.items() if prefs.get("stt")]
    with ThreadPoolExecutor(max_workers=len(tarefas) or 1) as pool:
        resultados = pool.map(lambda t: _candidato_stt(rec, dados, *t), tarefas)
        candidatos = [c for c in resultados if c]

    if not candidatos:
        return None, IDIOMA_PADRAO

    candidatos.sort(key=lambda t: t[0], reverse=True)
    _, texto, codigo = candidatos[0]
    return texto, codigo


def transcrever_audio(bytes_audio: bytes, codigo_forcado: str | None = None) -> tuple[str | None, str]:
    """
    Transcreve áudio.
    - codigo_forcado preenchido: usa apenas esse idioma (modo manual).
    - codigo_forcado=None: modo automático (Whisper identifica o idioma).
    """
    rec = obter_reconhecedor_stt()
    try:
        with sr.AudioFile(io.BytesIO(bytes_audio)) as src:
            dados = rec.record(src)
    except Exception as e:
        logger.warning("Falha ao ler o audio: %s", e, exc_info=True)
        return None, IDIOMA_PADRAO

    if codigo_forcado and codigo_forcado in MAPA_IDIOMAS:
        return _transcrever_forcado(rec, dados, codigo_forcado)

    return _transcrever_auto(rec, dados)


# =============================================================================
# Áudio — Text-to-Speech
# =============================================================================
def _limpar_texto_para_voz(texto: str) -> str:
    texto = re.sub(r"```.*?```", " ", texto, flags=re.DOTALL)
    for ch in ("*", "#", ">", "~", "_", "|", "`"):
        texto = texto.replace(ch, " ")
    return re.sub(r"\s+", " ", texto).strip()


async def _gerar_audio_edge(texto: str, caminho: str, voz: str) -> None:
    os.makedirs(DIRETORIO_AUDIO, exist_ok=True)
    await edge_tts.Communicate(texto, voz).save(caminho)


def gerar_audio_resposta(texto: str, id_msg: str) -> str | None:
    limpo = _limpar_texto_para_voz(texto)
    if not limpo:
        return None
    caminho = os.path.join(DIRETORIO_AUDIO, f"resp_{id_msg}.mp3")
    try:
        asyncio.run(_gerar_audio_edge(limpo, caminho, _prefs_idioma(_detectar_idioma(limpo))["voz_tts"]))
        return caminho
    except Exception as e:
        logger.warning("Falha ao gerar audio TTS: %s", e, exc_info=True)
        return None


def renderizar_audio_sequencial(b64: str) -> None:
    # Roda direto na página (sem iframe): o player e a fila ficam em window
    # e sobrevivem aos reruns.
    st.html(
        f"""
    <script>
    (function() {{
        const p = window;

        if (!p._ianaAudio) {{
            const el = p.document.createElement('audio');
            el.id = '_iana_audio_player';
            el.style.display = 'none';
            p.document.body.appendChild(el);

            p._ianaAudio = el;
            p._ianaQueue = [];
            p._ianaPlaying = false;

            p._ianaPlayNext = function() {{
                if (p._ianaPlaying || p._ianaQueue.length === 0) return;

                const src = p._ianaQueue.shift();
                const a = p._ianaAudio;
                p._ianaPlaying = true;

                a.onended = function() {{
                    p._ianaPlaying = false;
                    p._ianaPlayNext();
                }};
                a.onerror = function() {{
                    p._ianaPlaying = false;
                    p._ianaPlayNext();
                }};

                a.src = src;
                const promessa = a.play();
                if (promessa && promessa.catch) {{
                    promessa.catch(function(err) {{
                        console.warn('iAna: falha ao reproduzir áudio', err);
                        p._ianaPlaying = false;
                        p._ianaPlayNext();
                    }});
                }}
            }};
        }}

        p._ianaQueue.push("data:audio/mp3;base64,{b64}");
        p._ianaPlayNext();
    }})();
    </script>
    """,
        unsafe_allow_javascript=True,
    )
