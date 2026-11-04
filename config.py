import os

# 127.0.0.1 e não "localhost": no Windows, "localhost" tenta primeiro o IPv6
# (::1), onde o Ollama não escuta, e cada conexão nova perdia ~2 s.
URL_OLLAMA = "http://127.0.0.1:11434"
URL_OLLAMA_CHAT = URL_OLLAMA + "/api/chat"

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
    # 1024 cortava respostas longas (código, listas) no meio da frase.
    "num_predict": 2048,
    "temperature": 0.7,
    "top_p": 0.9,
}
# O modelo de visão tem num_ctx próprio (a regra do num_ctx igual vale por
# modelo). Com 16384 ele e o gemma4 ocupavam 11,8 de 12 GB da placa; 8192
# sobra para várias imagens e deixa folga para os dois ficarem carregados.
OLLAMA_OPTIONS_VISAO = {
    "num_ctx": 8192,
    "num_predict": 2048,
    "temperature": 0.3,
}

# Histórico enviado ao modelo a cada resposta. Antes eram só as 4 últimas
# mensagens: a iAna esquecia o que foi dito duas perguntas atrás.
HISTORICO_MAX_MENSAGENS = 16
HISTORICO_MAX_CHARS = 16000
# Com imagem, menos histórico: cada imagem pesa no contexto do modelo de visão.
HISTORICO_MAX_MENSAGENS_VISAO = 4

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
Quando a mensagem trouxer trechos da memória ou resultados da web, use-os se forem relevantes
e diga de onde veio a informação; ignore os que não tiverem relação com a pergunta.
Não cumprimente nem repita o nome da pessoa a cada resposta: vá direto ao ponto.
"""

# Acrescentado ao SYSTEM_PROMPT quando há imagem. Sem isso o minicpm-v
# respondia "não consigo ver imagens" em metade das vezes.
COMPLEMENTO_PROMPT_VISAO = "Você consegue ver as imagens anexadas pelo usuário nesta conversa. Analise-as diretamente."

PROMPT_PADRAO_IMAGEM ="""
Analise a imagem fornecida e descreva detalhadamente o que vê. 
Se houver texto na imagem, transcreva-o. 
Responda sempre em português.
"""