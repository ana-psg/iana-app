"""
Módulo de Interface Gráfica (UI/UX) e Componentes Visuais.
"""
import os
import re
import html
import base64
import logging
from datetime import datetime
from urllib.parse import quote
import streamlit as st

from config import (
    EXTENSOES_DOC, EXTENSOES_IMG, NOME_USUARIO, DIRETORIO_ICONES
)
from storage import (
    criar_nova_sessao, listar_conversas_cached, carregar_metadados_conversas,
    salvar_conversa, obter_nome_exibicao, apagar_todo_historico, imagens_da_mensagem,
    caminho_audio, avisar
)
from media import extrair_conteudo_documento, processar_imagem_otimizada, transcrever_audio
from brain import adicionar_a_memoria, remover_da_memoria, apagar_toda_memoria

logger = logging.getLogger(__name__)

DIRETORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))

_MAPA_IDIOMA_UI = {
    "PT": "pt",
    "EN": "en",
    "ES": "es",
    "FR": "fr",
}
_OPCOES_IDIOMA = ["Auto", "PT", "EN", "ES", "FR"]

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
# Design System
# =============================================================================
ESTILO_CUSTOMIZADO = """
<style>
/* ---------- Tokens: dark ---------- */
html[data-iana-theme="dark"] {
    --bg-base: #0A0A0C;
    --bg-surface: #131316;
    --bg-elevated: #1C1C20;
    --bg-hover: #232328;
    --bg-active: #2A2A30;
    --bg-input: #1C1C20;
    --border-subtle: #222226;
    --border-strong: #2E2E34;
    --text-primary: #EFEFF2;
    --text-secondary: #B4B4BC;
    --text-muted: #7A7A82;
    --accent: #FF8C42;
    --accent-soft: rgba(255, 140, 66, 0.14);
    --toggle-on: #22C55E;
    --shadow-panel: 0 8px 40px rgba(0,0,0,0.4);
    --shadow-card: 0 1px 2px rgba(0,0,0,0.3), 0 4px 16px rgba(0,0,0,0.25);
    --shadow-card-hover: 0 2px 4px rgba(0,0,0,0.35), 0 12px 32px rgba(0,0,0,0.35);
}

/* ---------- Tokens: light ---------- */
html[data-iana-theme="light"] {
    --bg-base: #F4F4F7;
    --bg-surface: #FFFFFF;
    --bg-elevated: #F0F0F4;
    --bg-hover: #E8E8ED;
    --bg-active: #DDDDE5;
    --bg-input: #F3F4F6;
    --border-subtle: #E5E5EB;
    --border-strong: #D5D5DD;
    --text-primary: #131316;
    --text-secondary: #4B4B52;
    --text-muted: #7A7A82;
    --accent: #E67E22;
    --accent-soft: rgba(230, 126, 34, 0.12);
    --toggle-on: #22C55E;
    --shadow-panel: 0 8px 40px rgba(0,0,0,0.06);
    --shadow-card: 0 1px 2px rgba(15,23,42,0.04), 0 4px 16px rgba(15,23,42,0.06);
    --shadow-card-hover: 0 2px 4px rgba(15,23,42,0.06), 0 12px 32px rgba(15,23,42,0.10);
}

/* ---------- Reset ---------- */
html, body, .stApp {
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif;
    font-feature-settings: "cv11", "ss01";
}
header[data-testid="stHeader"] {
    background-color: transparent !important;
    border-bottom: none !important;
    box-shadow: none !important;
}
header[data-testid="stHeader"] > div { background-color: transparent !important; }
[data-testid="stToolbar"] { background: transparent !important; }
[data-testid="stToolbar"] button { color: var(--text-secondary) !important; }
[data-testid="stToolbar"] button:hover { color: var(--accent) !important; }

[data-testid="stMainMenu"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stMainMenu"] button { color: var(--text-secondary) !important; }
[data-testid="stMainMenu"] button:hover {
    color: var(--accent) !important;
    background-color: var(--bg-hover) !important;
}

footer { display: none !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border-subtle) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
}
[data-testid="stSidebarHeader"] {
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
    border: none !important;
}
[data-testid="stSidebarHeader"] > div {
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="stSidebarContent"] { padding-top: 0.75rem !important; }
[data-testid="stSidebar"] * { color: var(--text-secondary) !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: var(--text-primary) !important; }

/* ---------- Botões nativos de collapse ---------- */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarNavCollapseButton"],
[data-testid="stCollapsedControl"],
[data-testid="collapsedControl"],
button[kind="header"],
button[kind="headerNoPadding"],
button[aria-label="Close sidebar"],
button[aria-label="Open sidebar"],
button[aria-label="close sidebar"],
button[aria-label="open sidebar"],
button[title="Close sidebar"],
button[title="Open sidebar"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* ---------- Botão gancho ---------- */
.st-key-nav_trigger_hidden,
[class*="st-key-nav_trigger_hidden"] {
    position: absolute !important;
    left: -9999px !important;
    top: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    clip: rect(0, 0, 0, 0) !important;
    clip-path: inset(50%) !important;
}

/* ---------- Botão primário ---------- */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #EC4899 0%, #EF4444 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    height: 40px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.01em !important;
    box-shadow: 0 2px 10px rgba(236, 72, 153, 0.22) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #DB2777 0%, #DC2626 100%) !important;
    box-shadow: 0 4px 16px rgba(236, 72, 153, 0.32) !important;
    transform: translateY(-1px) !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] * { color: #FFFFFF !important; }

/* ---------- Botões secundários ---------- */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background-color: var(--bg-input) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    height: 38px !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background-color: var(--bg-hover) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-strong) !important;
}

/* ---------- Toggle verde ---------- */
[data-testid="stSidebar"] [data-baseweb="checkbox"] div:first-child,
[data-testid="stSidebar"] [role="switch"][aria-checked="true"],
[data-testid="stSidebar"] label:has(input[type="checkbox"]:checked) > div:first-child {
    background-color: var(--toggle-on) !important;
    border-color: var(--toggle-on) !important;
}

/* ---------- Inputs sidebar ---------- */
[data-testid="stSidebar"] input[type="text"],
[data-testid="stSidebar"] textarea {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-size: 13.5px !important;
    padding: 8px 12px !important;
    transition: border-color 0.15s ease !important;
    box-shadow: none !important;
    outline: none !important;
}
[data-testid="stSidebar"] input[type="text"]:focus,
[data-testid="stSidebar"] input[type="text"]:focus-visible,
[data-testid="stSidebar"] textarea:focus,
[data-testid="stSidebar"] textarea:focus-visible {
    border-color: var(--border-strong) !important;
    box-shadow: none !important;
    outline: none !important;
}
[data-testid="stSidebar"] input[type="text"]::placeholder { color: var(--text-muted) !important; }

[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] [data-baseweb="base-input"] {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}
[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
[data-testid="stSidebar"] [data-baseweb="input"]:focus-within > div {
    border-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
}

/* ---------- Select sidebar ---------- */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    min-height: 38px !important;
    box-shadow: none !important;
    outline: none !important;
    transition: border-color 0.15s ease !important;
}
[data-testid="stSidebar"] [data-baseweb="select"]:hover > div {
    border-color: var(--border-strong) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:focus,
[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-visible {
    border-color: var(--border-strong) !important;
    box-shadow: none !important;
    outline: none !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg { color: var(--text-muted) !important; }
[data-baseweb="popover"] [role="listbox"] {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 10px !important;
}
[data-baseweb="popover"] [role="option"] {
    color: var(--text-secondary) !important;
    background-color: transparent !important;
}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"][aria-selected="true"] {
    background-color: var(--bg-hover) !important;
    color: var(--text-primary) !important;
}
[data-testid="stSidebar"] *:focus,
[data-testid="stSidebar"] *:focus-visible { outline: none !important; }

/* ---------- Expander conversas ---------- */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    background-color: transparent !important;
    overflow: hidden !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-weight: 600 !important;
    font-size: 13px !important;
    color: var(--text-primary) !important;
    padding: 10px 12px !important;
    margin: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    background-color: var(--bg-hover) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] > details > div,
[data-testid="stSidebar"] [data-testid="stExpander"] > details > div > div,
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"],
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
    padding: 0 !important;
}

/* ---------- Bloco de conversas ---------- */
.conv-block {
    padding: 0 10px 12px 10px;
    margin: 0;
}
.conv-block:first-of-type { padding-top: 8px; }
.conv-group {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 8px 4px 8px 4px;
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
    letter-spacing: 0.02em;
    user-select: none;
    line-height: 1.2;
}
.conv-group .chev {
    font-size: 10px;
    opacity: 0.6;
    transform: translateY(-1px);
}
.conv-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0;
    margin: 0;
}
.conv-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    margin: 0;
    border-radius: 10px;
    text-decoration: none !important;
    color: var(--text-secondary);
    font-size: 13px;
    line-height: 1.4;
    background-color: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    transition: background-color 0.12s ease, color 0.12s ease, border-color 0.12s ease;
    cursor: pointer;
    outline: none;
    box-sizing: border-box;
}
.conv-item:hover,
.conv-item:focus {
    background-color: var(--bg-hover);
    border-color: var(--border-strong);
    color: var(--text-primary);
    outline: none;
}
.conv-item.active {
    background-color: var(--bg-active);
    border-color: var(--border-strong);
    color: var(--text-primary);
    font-weight: 500;
}
.conv-item.active .conv-icon { opacity: 0.85; }
.conv-item .conv-icon {
    flex-shrink: 0;
    width: 15px;
    height: 15px;
    opacity: 0.55;
}
.conv-item .conv-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: inherit;
}
.conv-empty {
    padding: 14px;
    font-size: 12.5px;
    color: var(--text-muted);
    text-align: center;
}

/* ---------- Conteúdo principal ---------- */
.block-container {
    max-width: 780px !important;
    padding-top: 2rem !important;
    padding-bottom: 60px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    margin: 1.5rem auto !important;
}

/* ---------- Aproximar chat input da base ---------- */
[data-testid="stBottom"] {
    padding-bottom: 12px !important;
    padding-top: 0 !important;
}
[data-testid="stBottom"] > div {
    padding-bottom: 12px !important;
    padding-top: 0 !important;
}
[data-testid="stBottomBlockContainer"] {
    padding-bottom: 12px !important;
    padding-top: 0 !important;
}

/* ---------- Chat ---------- */
[data-testid="stChatMessage"] {
    background-color: transparent !important;
    padding: 0.5rem 0 !important;
}
[data-testid="stChatMessageContent"] {
    color: var(--text-primary) !important;
    font-size: 15px !important;
    line-height: 1.65 !important;
}
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] {
    background-color: var(--accent-soft) !important;
    border: 1px solid var(--accent) !important;
}
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] {
    background-color: var(--bg-elevated) !important;
    border: 1px solid var(--border-subtle) !important;
}

/* ---------- Input de chat ---------- */
[data-testid="stChatInputContainer"],
[data-testid="stChatInput"] {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 26px !important;
    box-shadow: var(--shadow-panel) !important;
}
[data-testid="stChatInputContainer"] textarea,
[data-testid="stChatInput"] textarea {
    background-color: transparent !important;
    color: var(--text-primary) !important;
    font-size: 14.5px !important;
}
[data-testid="stChatInputContainer"] textarea::placeholder,
[data-testid="stChatInput"] textarea::placeholder { color: var(--text-muted) !important; }
[data-testid="stChatInputContainer"] button,
[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] {
    background-color: var(--bg-elevated) !important;
    color: var(--text-secondary) !important;
    border: none !important;
    border-radius: 50% !important;
    transition: all 0.15s ease !important;
}
[data-testid="stChatInputContainer"] button:hover,
[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:hover {
    background-color: var(--bg-hover) !important;
    color: var(--text-primary) !important;
}

/* ---------- Seletor de idioma (st.popover nativo) ---------- */
.st-key-footer_lang,
.st-key-footer_lang > div,
.st-key-footer_lang [data-testid="stVerticalBlock"],
.st-key-footer_lang [data-testid="stPopover"],
.st-key-footer_lang [data-testid="stPopover"] > div {
    height: 46px !important;
    min-height: 46px !important;
    max-height: 46px !important;
    width: 100% !important;
}
.st-key-footer_lang [data-testid="stPopover"] > button {
    width: 100% !important;
    height: 46px !important;
    min-height: 46px !important;
    max-height: 46px !important;
    padding: 0 10px !important;
    background: var(--bg-input) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    color: var(--text-secondary) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 4px !important;
    box-shadow: none !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    transition: all 0.15s ease !important;
    text-transform: uppercase !important;
}
.st-key-footer_lang [data-testid="stPopover"] > button:hover {
    background: var(--bg-hover) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-strong) !important;
}
.st-key-footer_lang [data-testid="stPopover"] > button * {
    color: inherit !important;
    white-space: nowrap !important;
}
.st-key-footer_lang [data-testid="stPopover"] > button > div {
    display: flex !important;
    align-items: center !important;
    gap: 4px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
}
.st-key-footer_lang [data-testid="stPopover"] > button p {
    white-space: nowrap !important;
    margin: 0 !important;
    word-break: keep-all !important;
    overflow-wrap: normal !important;
}
.st-key-footer_lang [data-testid="stPopover"] > button svg {
    width: 10px !important;
    height: 10px !important;
    opacity: 0.7 !important;
    flex-shrink: 0 !important;
}

/* Painel do popover (o menu que abre). */
[data-testid="stPopoverBody"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    padding: 6px !important;
    box-shadow: var(--shadow-panel) !important;
    min-width: 90px !important;
}
[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] {
    gap: 2px !important;
}
[data-testid="stPopoverBody"] .stButton > button {
    width: 100% !important;
    height: 30px !important;
    min-height: 30px !important;
    padding: 0 10px !important;
    border-radius: 8px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    background: transparent !important;
    color: var(--text-secondary) !important;
    border: none !important;
    box-shadow: none !important;
    transition: all 0.12s ease !important;
    text-transform: uppercase !important;
}
[data-testid="stPopoverBody"] .stButton > button:hover {
    background: var(--bg-hover) !important;
    color: var(--text-primary) !important;
}
[data-testid="stPopoverBody"] .stButton > button[kind="primary"] {
    background: var(--bg-active) !important;
    color: var(--accent) !important;
}
[data-testid="stPopoverBody"] .stButton > button[kind="primary"] * {
    color: var(--accent) !important;
}

/* ---------- Mic (st.audio_input) ---------- */
/* Container rígido em 46x46. Nada dentro pode estourar. */
.st-key-footer_mic,
.st-key-footer_mic > div,
.st-key-footer_mic [data-testid="stVerticalBlock"] {
    width: 46px !important;
    height: 46px !important;
    min-height: 46px !important;
    max-height: 46px !important;
}

.st-key-footer_mic [data-testid="stAudioInput"],
.st-key-footer_mic [data-testid="stAudioInput"] > div {
    width: 46px !important;
    height: 46px !important;
    min-height: 46px !important;
    max-height: 46px !important;
    overflow: hidden !important;
    position: relative !important;
}

/* O botão do mic é fixado em 46x46 e recebe visibility:hidden —
   isso propaga para TODO filho (timer, spans, waveform). O SVG é
   restaurado logo abaixo com visibility:visible. */
.st-key-footer_mic [data-testid="stAudioInput"] button {
    position: absolute !important;
    inset: 0 !important;
    width: 46px !important;
    height: 46px !important;
    min-width: 46px !important;
    max-width: 46px !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: var(--bg-input) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    color: var(--text-secondary) !important;
    overflow: hidden !important;
    visibility: hidden !important;   /* esconde tudo: texto, timer, play, etc */
    z-index: 2 !important;           /* acima do container vazio da onda sonora, que cobria o ícone */
    font-size: 0 !important;
    line-height: 0 !important;
    transition: background 0.15s ease, border-color 0.15s ease !important;
}

/* Só o SVG volta a aparecer. */
.st-key-footer_mic [data-testid="stAudioInput"] button svg,
.st-key-footer_mic [data-testid="stAudioInput"] button svg * {
    visibility: visible !important;
    display: inline-block !important;
    width: 18px !important;
    height: 18px !important;
    color: var(--text-secondary) !important;
    flex-shrink: 0 !important;
}

.st-key-footer_mic [data-testid="stAudioInput"] button:hover {
    background: var(--bg-hover) !important;
    border-color: var(--border-strong) !important;
}
.st-key-footer_mic [data-testid="stAudioInput"] button:hover svg,
.st-key-footer_mic [data-testid="stAudioInput"] button:hover svg * {
    color: var(--text-primary) !important;
}

/* A onda sonora (WaveSurfer) tem z-index internos que cobriam o botão de
   parar a gravação. isolation confina esses z-index numa camada abaixo do
   botão, e pointer-events deixa o clique passar. */
.st-key-footer_mic [data-testid="stAudioInputWaveSurfer"] {
    isolation: isolate !important;
    z-index: 0 !important;
    pointer-events: none !important;
}

/* Botões extras (play) e players ficam completamente escondidos. */
.st-key-footer_mic [data-testid="stAudioInput"] button ~ button,
.st-key-footer_mic [data-testid="stAudioInput"] [data-testid*="waveform" i],
.st-key-footer_mic [data-testid="stAudioInput"] audio {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
}

/* ---------- Cards de sugestão ---------- */
.st-key-sug_row [data-testid="stHorizontalBlock"] {
    display: flex !important;
    align-items: stretch !important;
}
.st-key-sug_row [data-testid="column"] {
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
}
.st-key-sug_row [data-testid="column"] > div {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    width: 100% !important;
}
.st-key-sug_row [data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    height: 100% !important;
    gap: 0 !important;
}

.sug-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 16px 16px 0 0;
    border-bottom: none;
    padding: 20px 20px 14px 20px;
    flex: 1 1 auto;
    min-height: 172px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    box-shadow: var(--shadow-card);
}
.sug-card:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow-card-hover);
}
.sug-icon { font-size: 26px; margin-bottom: 12px; line-height: 1; }
.sug-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 6px;
    line-height: 1.35;
}
.sug-desc {
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.45;
    flex-grow: 1;
    /* Reserva 3 linhas: os cards ficam da mesma altura mesmo quando uma
       descrição quebra em mais linhas que as outras. Esticar pela altura
       da coluna depende da estrutura interna do Streamlit, que muda. */
    min-height: calc(1.45em * 3);
}
.sug-tag {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
}

[class*="st-key-sug_"][class*="_card"] {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    height: 100% !important;
}
[class*="st-key-sug_"][class*="_card"] [data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    gap: 0 !important;
}
[class*="st-key-sug_"][class*="_card"] .stMarkdown {
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
}
[class*="st-key-sug_"][class*="_card"] .stMarkdown > div {
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
}
[class*="st-key-sug_"][class*="_card"] .sug-card {
    flex: 1 !important;
}
[class*="st-key-sug_"][class*="_card"] .stButton {
    margin: 0 !important;
    margin-top: -1px !important;
    flex-shrink: 0 !important;
}
[class*="st-key-sug_"][class*="_card"] .stButton > button {
    background-color: var(--bg-surface) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-top-left-radius: 0 !important;
    border-top-right-radius: 0 !important;
    border-bottom-left-radius: 16px !important;
    border-bottom-right-radius: 16px !important;
    height: 42px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    box-shadow: var(--shadow-card) !important;
    transition: all 0.15s ease !important;
}
[class*="st-key-sug_"][class*="_card"] .stButton > button:hover {
    background-color: var(--bg-hover) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-strong) !important;
    box-shadow: var(--shadow-card-hover) !important;
}

/* ---------- Greeting centralizado ---------- */
.greeting-wrap {
    text-align: center;
    padding: 3rem 0 2.5rem 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.greeting-avatar {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: linear-gradient(135deg, #EC4899 0%, #EF4444 100%);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 20px;
    box-shadow: 0 6px 20px rgba(236, 72, 153, 0.32);
}
.greeting-avatar svg { display: block; }
.greeting-title {
    font-size: 26px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin: 0 0 10px 0;
    text-align: center;
}
.greeting-sub {
    font-size: 14px;
    color: var(--text-muted);
    margin: 0;
    text-align: center;
    max-width: 520px;
    line-height: 1.5;
}

/* ---------- Chip de anexo ---------- */
.st-key-chip_doc .stButton > button {
    padding: 4px 12px !important;
    min-height: 0 !important;
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    font-size: 12.5px !important;
    color: var(--text-secondary) !important;
}
.st-key-chip_doc .stButton > button:hover {
    border-color: var(--border-strong) !important;
    color: var(--text-primary) !important;
}

/* ---------- Código ---------- */
[data-testid="stCodeBlock"] {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
}

/* ---------- Copiar resposta ---------- */
.iana-copy {
    display: flex;
    justify-content: flex-end;
    padding-top: 4px;
}
.iana-copy-btn {
    background: transparent;
    border: 1px solid var(--border-strong);
    color: var(--text-muted);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.14s ease;
}
.iana-copy-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}
.iana-copy-btn.ok {
    color: #4ADE80;
    border-color: #4ADE80;
}

/* ---------- Toast ---------- */
[data-testid="stToast"] {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
}
</style>
"""

# Define o tema dos tokens CSS (data-iana-theme). O detector antigo lia a cor
# de fundo do app, mas essa cor vem do nosso próprio CSS (que depende do tema):
# era circular e sempre resultava em "dark". Agora o tema vem do Streamlit
# (st.context.theme, que ignora CSS customizado) e, quando ele ainda não sabe,
# da preferência do sistema, que é o que o Streamlit segue por padrão.
SCRIPT_TEMA = """
<script>
(function() {
    let tema = '__TEMA__';
    if (tema !== 'light' && tema !== 'dark') {
        tema = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-iana-theme', tema);
})();
</script>
"""

SCRIPT_TOGGLE_SIDEBAR = """
<script>
(function() {
    const p = window;
    const doc = p.document;

    // Roda na própria página (st.html): o botão sobrevive aos reruns,
    // então só é criado uma vez.
    if (doc.getElementById('iana-sidebar-toggle')) return;

    const btn = doc.createElement('button');
    btn.id = 'iana-sidebar-toggle';
    btn.setAttribute('aria-label', 'Alternar barra lateral');
    btn.style.cssText = [
        'position: fixed',
        'top: 12px',
        'left: 12px',
        'width: 28px',
        'height: 28px',
        'border-radius: 8px',
        'border: 1px solid #222226',
        'background: #1C1C20',
        'color: #B4B4BC',
        'cursor: pointer',
        'display: flex',
        'align-items: center',
        'justify-content: center',
        'z-index: 2147483000',
        'padding: 0',
        'font-size: 15px',
        'line-height: 1',
        'font-weight: 700',
        'font-family: -apple-system, BlinkMacSystemFont, sans-serif',
        'pointer-events: auto',
        'user-select: none',
        'transition: left 0.25s ease, background 0.15s ease, color 0.15s ease, border-color 0.15s ease'
    ].join(';');

    function cores() {
        const isDark = (doc.documentElement.getAttribute('data-iana-theme') || 'dark') === 'dark';
        return {
            bg: isDark ? '#1C1C20' : '#F0F0F4',
            border: isDark ? '#222226' : '#E5E5EB',
            text: isDark ? '#B4B4BC' : '#4B4B52'
        };
    }

    let ultimoEstado = '';
    function atualizar(forcar) {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const r = sidebar ? sidebar.getBoundingClientRect() : null;
        const aberta = !!r && r.width > 60 && r.right > 40;
        const left = aberta ? (r.right + 18) + 'px' : '12px';
        const tema = doc.documentElement.getAttribute('data-iana-theme') || 'dark';

        // Só mexe no DOM quando algo mudou. Antes reescrevia a cada 200 ms,
        // o que também apagava a cor de hover logo após o mouse entrar.
        const estado = aberta + '|' + left + '|' + tema;
        if (estado === ultimoEstado && forcar !== true) return;
        ultimoEstado = estado;

        btn.textContent = aberta ? '‹' : '›';
        btn.style.left = left;

        const c = cores();
        btn.style.background = c.bg;
        btn.style.borderColor = c.border;
        btn.style.color = c.text;
    }

    function disparar() {
        const candidatos = [
            '[data-testid="stSidebarCollapseButton"] button',
            '[data-testid="stSidebarCollapsedControl"] button',
            '[data-testid="stExpandSidebarButton"] button',
            '[data-testid="stSidebarNavCollapseButton"] button',
            '[data-testid="stCollapsedControl"] button',
            '[data-testid="collapsedControl"] button',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="stSidebarCollapsedControl"]',
            '[data-testid="stExpandSidebarButton"]',
            '[data-testid="stSidebarNavCollapseButton"]',
            '[data-testid="stCollapsedControl"]',
            '[data-testid="collapsedControl"]',
            'button[kind="header"]',
            'button[kind="headerNoPadding"]',
            'button[aria-label="Close sidebar"]',
            'button[aria-label="Open sidebar"]',
            'button[aria-label="close sidebar"]',
            'button[aria-label="open sidebar"]',
            'button[title="Close sidebar"]',
            'button[title="Open sidebar"]',
        ];
        for (const s of candidatos) {
            const el = doc.querySelector(s);
            if (el) { el.click(); return true; }
        }
        return false;
    }

    btn.addEventListener('click', function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        disparar();
        setTimeout(atualizar, 60);
        setTimeout(atualizar, 320);  // depois da animação da sidebar
    });

    btn.addEventListener('mouseenter', function() {
        btn.style.color = '#EC4899';
        btn.style.borderColor = '#EC4899';
    });
    btn.addEventListener('mouseleave', function() { atualizar(true); });

    doc.body.appendChild(btn);

    atualizar(true);
    setInterval(atualizar, 300);
})();
</script>
"""

SCRIPT_NAV_SUAVE = """
<script>
(function() {
    const p = window;
    const doc = p.document;

    if (p._ianaConvNavAttached) return;
    p._ianaConvNavAttached = true;

    doc.addEventListener('click', function(e) {
        const a = e.target && e.target.closest ? e.target.closest('a.conv-item') : null;
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || !href.startsWith('?load_conv=')) return;

        e.preventDefault();
        e.stopPropagation();

        try {
            p.history.pushState({}, '', href);
        } catch (err) {
            p.location.href = href;
            return;
        }

        const ganchos = [
            '.st-key-nav_trigger_hidden button',
            '[class*="st-key-nav_trigger_hidden"] button',
        ];
        for (const s of ganchos) {
            const b = doc.querySelector(s);
            if (b) { b.click(); return; }
        }
        p.location.href = href;
    }, true);
})();
</script>
"""

# Um único listener para todos os botões "Copiar resposta". Antes cada
# resposta tinha o próprio iframe com JS.
SCRIPT_COPIAR = """
<script>
(function() {
    if (window._ianaCopiarAtivo) return;
    window._ianaCopiarAtivo = true;

    document.addEventListener('click', function(e) {
        const btn = e.target && e.target.closest ? e.target.closest('.iana-copy-btn') : null;
        if (!btn) return;
        const raw = btn.parentElement.querySelector('.iana-raw');
        if (!raw) return;
        navigator.clipboard.writeText(raw.value).then(function() {
            btn.textContent = 'Copiado!';
            btn.classList.add('ok');
            setTimeout(function() {
                btn.textContent = 'Copiar resposta';
                btn.classList.remove('ok');
            }, 1500);
        });
    });
})();
</script>
"""

# =============================================================================
# Inicialização
# =============================================================================
def inicializar_interface() -> None:
    favicon = ICONE_FAVICON if ICONE_FAVICON else None
    st.set_page_config(page_title="iAna", page_icon=favicon, layout="wide")
    # CSS via st.html vai para um container de eventos e não ocupa espaço.
    st.html(ESTILO_CUSTOMIZADO)
    # Scripts rodam direto na página, sem iframes (components.v1.html está
    # obsoleto). Cada script se protege contra reexecução nos reruns.
    st.html(
        SCRIPT_TEMA.replace("__TEMA__", st.context.theme.type or "")
        + SCRIPT_TOGGLE_SIDEBAR + SCRIPT_NAV_SUAVE + SCRIPT_COPIAR,
        unsafe_allow_javascript=True,
    )

# =============================================================================
# Item de conversa
# =============================================================================
_SVG_CHAT = (
    '<svg class="conv-icon" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
    '</svg>'
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
            f'{_SVG_CHAT}'
            f'<span class="conv-name">{nome}</span>'
            f'</a>'
        )
    html_bloco = (
        f'<div class="conv-block">'
        f'<div class="conv-group">{titulo} <span class="chev">⌄</span></div>'
        f'<div class="conv-list">{"".join(itens)}</div>'
        f'</div>'
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
            '<hr style="border:none; border-top:1px solid var(--border-subtle); '
            'margin:1rem 0 1.1rem 0;">',
            unsafe_allow_html=True
        )

        novo_proj = st.text_input(
            "Novo projeto",
            placeholder="Nome do projeto...",
            label_visibility="collapsed",
            key="input_novo_projeto"
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
            unsafe_allow_html=True
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
                st.markdown(
                    '<div class="conv-empty">Nenhuma conversa ainda.</div>',
                    unsafe_allow_html=True
                )

        st.markdown(
            '<hr style="border:none; border-top:1px solid var(--border-subtle); '
            'margin:1.1rem 0;">',
            unsafe_allow_html=True
        )
        if st.button("Apagar todo o histórico", use_container_width=True, type="secondary"):
            _confirmar_apagar_historico()

    return {"pesquisa_web": pesquisa_web}

# =============================================================================
# Botão copiar resposta
# =============================================================================
def _renderizar_botao_copiar(texto: str) -> None:
    # O texto bruto (markdown) fica num textarea oculto; o SCRIPT_COPIAR,
    # carregado uma vez, copia ao clicar. html.escape impede que a resposta
    # do modelo vire HTML.
    st.html(
        '<div class="iana-copy">'
        f'<textarea class="iana-raw" hidden>{html.escape(texto)}</textarea>'
        '<button class="iana-copy-btn" type="button">Copiar resposta</button>'
        '</div>'
    )

# =============================================================================
# Resposta formatada
# =============================================================================
def renderizar_resposta_formatada(texto: str) -> None:
    padrao_bloco = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
    pos = 0
    for match in padrao_bloco.finditer(texto):
        antes = texto[pos:match.start()].strip()
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
            avisar(f"Não consegui ler o texto de {arq_doc.name}. Se for um PDF escaneado (só imagem), envie como imagem.")
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

    if idioma_atual == "Auto":
        label = "Auto | PT"
    else:
        label = idioma_atual

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
    '</svg>'
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
        '</div>',
        unsafe_allow_html=True
    )

    with st.container(key="sug_row"):
        col1, col2, col3 = st.columns(3, gap="small")

        with col1:
            with st.container(key="sug_doc_card"):
                st.markdown(
                    '<div class="sug-card">'
                    '<div class="sug-icon">📄</div>'
                    '<div class="sug-title">Analisar um documento</div>'
                    '<div class="sug-desc">Envie um PDF ou DOCX e pergunte qualquer coisa sobre o conteúdo.</div>'
                    '<div class="sug-tag">RAG · MEMÓRIA</div>'
                    '</div>',
                    unsafe_allow_html=True
                )
                if st.button("Analisar documento", key="sug_doc", use_container_width=True):
                    _preparar_pedido_com_anexo("documento", "Resuma o documento que enviei.")

        with col2:
            with st.container(key="sug_img_card"):
                st.markdown(
                    '<div class="sug-card">'
                    '<div class="sug-icon">🖼️</div>'
                    '<div class="sug-title">Analisar uma imagem</div>'
                    '<div class="sug-desc">Arraste uma foto e peça uma descrição, tradução ou transcrição.</div>'
                    '<div class="sug-tag">VISÃO · MINICPM-V</div>'
                    '</div>',
                    unsafe_allow_html=True
                )
                if st.button("Analisar imagem", key="sug_img", use_container_width=True):
                    _preparar_pedido_com_anexo("imagem", "Descreva detalhadamente a imagem.")

        with col3:
            with st.container(key="sug_web_card"):
                st.markdown(
                    '<div class="sug-card">'
                    '<div class="sug-icon">✦</div>'
                    '<div class="sug-title">Pesquisar na web</div>'
                    '<div class="sug-desc">Pergunte sobre algo atual — cotações, notícias, eventos recentes.</div>'
                    '<div class="sug-tag">DUCKDUCKGO</div>'
                    '</div>',
                    unsafe_allow_html=True
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
    col_input, col_mic, col_lang = st.columns(
        [1, 0.11, 0.22], gap="small", vertical_alignment="bottom"
    )

    with col_input:
        pedido_anexo = st.session_state.get("_pedido_com_anexo")
        submissao = st.chat_input(
            f"Anexe a {pedido_anexo['tipo']} pelo + e envie..." if pedido_anexo else "Pergunte qualquer coisa...",
            accept_file="multiple",
            file_type=EXTENSOES_DOC + EXTENSOES_IMG
        )

    with col_mic:
        with st.container(key="footer_mic"):
            mic_key = f"mic_{st.session_state.get('_mic_version', 0)}"
            audio = st.audio_input("Gravar", label_visibility="collapsed", key=mic_key)

    with col_lang:
        with st.container(key="footer_lang"):
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
            st.session_state.mensagens.append({
                "role": "user",
                "content": texto,
                "imagens_b64": imagens_b64
            })
            st.session_state.ultima_foi_voz = False
            st.session_state._pendente_processar = True
            st.rerun()
        elif documentos_indexados:
            st.rerun()

    if sugestao:
        st.session_state.mensagens.append({
            "role": "user",
            "content": sugestao,
            "imagens_b64": []
        })
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
        texto_voz, _ = transcrever_audio(
            pending["bytes"], codigo_forcado=pending["lang"]
        )
        if texto_voz:
            st.session_state.mensagens.append({
                "role": "user",
                "content": texto_voz,
                "imagens_b64": []
            })
            st.session_state.ultima_foi_voz = True
            st.session_state._pendente_processar = True
            st.rerun()
        elif pending["lang"]:
            avisar(f"Não entendi o áudio em {pending['lang'].upper()}. Tente de novo, ou volte o idioma para Auto.", "🎙️")
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