import os

URL_OLLAMA_CHAT = "http://localhost:11434/api/chat"
URL_OLLAMA_EMBED = "http://localhost:11434/api/embeddings"

# =============================================================================
# Modelos fixos da iAna
# =============================================================================
MODELO_TEXTO = "gemma4:e4b"
MODELO_VISAO = "minicpm-v"
# Multilíngue. O nomic-embed-text (anterior) não separava perguntas relevantes
# de irrelevantes em português e achava o documento certo em 10 de 14 testes;
# o bge-m3 acertou 14 de 14.
MODELO_EMBEDDING = "bge-m3"
# Trechos da memória mais distantes que isto não entram na resposta.
# Calibrado para o bge-m3: relevantes 0,27–0,49 (um a 0,56) e irrelevantes
# 0,51–0,73. Ao trocar o modelo de embeddings, recalibre.
RAG_DISTANCIA_MAX = 0.50

OLLAMA_KEEP_ALIVE = "30m"
# O gemma4 é um modelo de raciocínio: com think ligado ele gasta tokens
# pensando antes de responder (atrasa o 1º token e esvazia respostas curtas).
OLLAMA_THINK = False
# Todas as chamadas ao Ollama devem usar o MESMO num_ctx: um valor diferente
# força o Ollama a recarregar o modelo (~6 s a cada troca).
OLLAMA_NUM_CTX = 16384
OLLAMA_OPTIONS = {
    "num_ctx": OLLAMA_NUM_CTX,
    "num_predict": 1024,
    "temperature": 0.7,
    "top_p": 0.9,
}

# =============================================================================
# Diretórios do Projeto
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DIRETORIO_HISTORICO = os.path.join(BASE_DIR, "historico")
DIRETORIO_AUDIO = os.path.join(BASE_DIR, "audio")
DIRETORIO_MEMORIA = os.path.join(BASE_DIR, "memoria")
DIRETORIO_ICONES = os.path.join(BASE_DIR, "Icons")

# =============================================================================
# Configurações da Interface / Histórico
# =============================================================================
TAMANHO_MAX_TITULO = 50

EXTENSOES_DOC = ["pdf", "txt", "docx", "md", "csv"]
EXTENSOES_IMG = ["png", "jpg", "jpeg", "webp", "gif"]
NOME_USUARIO = ""

# =============================================================================
# Configurações de Mídia
# =============================================================================
LADO_MAX_IMAGEM = 1024

MAPA_IDIOMAS = {
    "pt": {"nome": "Português", "voz_tts": "pt-BR-FranciscaNeural", "stt": "pt-BR"},
    "en": {"nome": "Inglês",    "voz_tts": "en-US-AriaNeural",      "stt": "en-US"},
    "es": {"nome": "Espanhol",  "voz_tts": "es-ES-ElviraNeural",    "stt": "es-ES"},
    "fr": {"nome": "Francês",   "voz_tts": "fr-FR-DeniseNeural",    "stt": "fr-FR"},
}

IDIOMA_PADRAO = "pt"

# =============================================================================
# Prompts do Sistema
# =============================================================================
SYSTEM_PROMPT = """
Você é a iAna, uma assistente virtual inteligente, prestativa e amigável.
Você foi criada para ajudar o usuário com as suas tarefas diárias, responder a perguntas e analisar informações.
Responda no mesmo idioma da mensagem do usuário. Se não tiver certeza, responda em português.
Se não souber a resposta, diga que não sabe, em vez de inventar.
"""

# Acrescentado ao SYSTEM_PROMPT quando há imagem. Sem isso o minicpm-v
# respondia "não consigo ver imagens" em metade das vezes.
COMPLEMENTO_PROMPT_VISAO = "Você consegue ver as imagens anexadas pelo usuário nesta conversa. Analise-as diretamente."

PROMPT_PADRAO_IMAGEM ="""
Analise a imagem fornecida e descreva detalhadamente o que vê. 
Se houver texto na imagem, transcreva-o. 
Responda sempre em português.
"""