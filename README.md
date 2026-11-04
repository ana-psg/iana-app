# iAna

Assistente pessoal de IA com interface de chat, memória de longo prazo (RAG), análise de imagens e voz. O modelo de linguagem roda localmente no seu computador através do [Ollama](https://ollama.com).

<!-- Adicione aqui um print da interface:
![Tela da iAna](docs/screenshot.png)
-->

## Recursos

- Chat com respostas em streaming via Ollama, usando o modelo `gemma4:e4b`
- Memória vetorial (RAG) com ChromaDB: indexa documentos PDF, DOCX, TXT, Markdown e CSV, e recupera os trechos mais relevantes para responder
- Análise de imagens com o modelo `minicpm-v` (com contexto: RAG, histórico recente e resumo da conversa)
- Suporte a múltiplas imagens no mesmo histórico da conversa
- Entrada por voz e resposta em áudio (português, inglês, espanhol e francês) — no modo Auto o idioma falado é identificado localmente (Whisper) antes da transcrição; também é possível fixar o idioma
- Pesquisa na web (DuckDuckGo) quando a pergunta exige informação atual — desativada automaticamente quando há imagem anexada
- Histórico de conversas salvo em disco, organizado por projetos, com títulos automáticos e resumo incremental
- Botão para copiar respostas e blocos de código formatados

## Requisitos

- Python 3.13 ou superior (testado com o 3.14)
- [Ollama](https://ollama.com) instalado e em execução (por padrão em `http://localhost:11434`)
- Memória RAM/VRAM suficiente para os modelos. Em computadores modestos, as respostas podem ser lentas.

## Instalação no Windows

1. Instale o [Python](https://www.python.org/downloads/), marcando **"Add python.exe to PATH"**, e o [Ollama](https://ollama.com).
2. Nesta página, clique em **Code > Download ZIP** e descompacte a pasta onde quiser.
3. Dê dois cliques em **`instalar.bat`**. Ele instala tudo e pergunta se pode baixar os modelos de IA (são vários GB).
4. Abra a iAna com **`iAna.bat`**. O navegador abre sozinho; deixe a janela preta aberta enquanto usa.

## Instalação manual (Windows, Linux e macOS)

```bash
# 1. Clone o repositório
git clone https://github.com/ana-psg/iana-app.git
cd iana-app

# 2. Crie e ative um ambiente virtual
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Baixe os modelos no Ollama
ollama pull gemma4:e4b
ollama pull minicpm-v
ollama pull bge-m3

# 5. Execute o app
streamlit run app.py
```

O navegador abrirá automaticamente em `http://localhost:8501`.

## Configuração

As configurações ficam em `iana/config.py`:

| Constante | Função |
|---|---|
| `MODELO_TEXTO` | Modelo usado nas conversas (padrão: `gemma4:e4b`) |
| `MODELO_VISAO` | Modelo usado para analisar imagens (padrão: `minicpm-v`) |
| `MODELO_EMBEDDING` | Modelo de embeddings da memória (padrão: `bge-m3`, multilíngue) |
| `RAG_DISTANCIA_MAX` | Quão parecido um trecho precisa ser da pergunta para entrar na resposta |
| `NOME_USUARIO` | Seu nome na tela inicial (opcional) |
| `OLLAMA_OPTIONS` / `OLLAMA_NUM_CTX` | Contexto, temperatura e tamanho máximo da resposta |
| `OLLAMA_OPTIONS_VISAO` | Contexto e tamanho da resposta do modelo de visão |
| `HISTORICO_MAX_MENSAGENS` / `HISTORICO_MAX_CHARS` | Quanto da conversa é enviado ao modelo a cada resposta |
| `OLLAMA_THINK` | Raciocínio prévio do modelo (desligado: respostas bem mais rápidas) |
| `MAPA_IDIOMAS` | Idiomas e vozes da entrada e da resposta por voz |

Qualquer modelo disponível no Ollama pode ser usado, basta trocar o nome e executar `ollama pull` com ele. Todas as chamadas usam o mesmo `num_ctx`; valores diferentes fazem o Ollama recarregar o modelo a cada troca.

## Estrutura do projeto

```
iana-app/
├── app.py              # ponto de entrada do Streamlit (orquestra a interface e o fluxo)
├── iana/               # o app
│   ├── config.py         # modelos, diretórios, idiomas e prompts
│   ├── brain.py          # Ollama, memória vetorial (RAG), pesquisa web e resumo
│   ├── processor.py      # monta o contexto e gera cada resposta
│   ├── media.py          # documentos, imagens, voz (STT/TTS) e áudio
│   ├── storage.py        # conversas e projetos em disco
│   └── ui/               # interface
│       ├── recursos.py     # configuração da página, CSS e scripts
│       ├── sidebar.py      # projetos, conversas, histórico e memória
│       ├── chat.py         # boas-vindas, mensagens, anexos, voz e caixa de mensagem
│       └── assets/         # estilo.css (tokens e componentes) e um .js por comportamento
├── tests/              # testes automáticos (pytest), sem precisar do Ollama
├── instalar.bat        # instala tudo no Windows
├── iAna.bat            # abre o app no Windows
├── Icons/              # ícones da aba do navegador
├── requirements.txt    # dependências Python (requirements-dev.txt: testes e lint)
└── README.md
```

Ao rodar, o app cria automaticamente estas pastas ao lado do `app.py`:

- `historico/`: suas conversas em arquivos JSON
- `memoria/`: banco vetorial com os documentos que você indexou
- `audio/`: áudios gerados nas respostas por voz

## Dados e privacidade

Suas conversas e documentos ficam armazenados somente no seu computador, nas pastas acima, que estão no `.gitignore` e não são enviadas ao GitHub.

O modelo de linguagem roda localmente, mas alguns recursos usam serviços online:

- **Reconhecimento de voz**: o áudio gravado é enviado ao serviço de reconhecimento do Google
- **Resposta em voz**: a síntese de fala usa o serviço online do edge-tts (Microsoft)
- **Pesquisa na web**: as consultas são enviadas ao DuckDuckGo

Se você quiser uso totalmente offline, evite os recursos de voz e de pesquisa na web.

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
python -m pytest
```

Os testes usam pastas temporárias e nunca tocam nas suas conversas nem na memória.

## Limitações

- Como qualquer modelo de linguagem, a iAna pode errar ou inventar informações. Confira dados importantes.
- PDFs escaneados (apenas imagem, sem texto selecionável) podem não ter texto extraível.
- A qualidade das respostas depende do modelo escolhido no Ollama.

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).

Os modelos baixados pelo Ollama (gemma4, minicpm-v, bge-m3) têm licenças próprias, definidas por seus autores. Consulte-as antes de qualquer uso comercial.
