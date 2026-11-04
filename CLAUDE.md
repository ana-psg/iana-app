# iAna (repo iana-app)

Assistente pessoal de IA local: chat com Ollama, memória de documentos (RAG com ChromaDB), imagens e voz.
Streamlit, roda só em localhost (`.streamlit/config.toml`).

## Estrutura
- `app.py` (raiz) é o ponto de entrada do Streamlit (`streamlit run app.py`; o `iAna.bat` chama ele).
- Pacote `iana/`: `config.py`, `storage.py` (conversas em JSON), `brain.py` (Ollama, RAG, web, resumo),
  `processor.py` (monta o contexto e gera a resposta), `media.py` (documentos, imagens, voz),
  `ui/` (`recursos.py` página/CSS/scripts, `sidebar.py`, `chat.py`, `assets/` com estilo.css e os .js).
- `tests/` (pytest, sem Ollama). Dados (`historico/`, `memoria/`, `audio/`) ficam na raiz e nunca vão ao Git.

## Regras
- Código, telas e mensagens em português do Brasil.
- Visual: tokens CSS em `iana/ui/assets/estilo.css` nos dois temas (`html[data-iana-theme="dark"|"light"]`).
  Cor nova entra como token nos dois. O CSS mira seletores internos do Streamlit (`data-testid`): ao subir a
  versão do Streamlit, conferir as telas.
- Scripts da página ficam em `iana/ui/assets/*.js`, cada um protegido contra reexecução nos reruns.
- Texto vindo de pessoa ou do modelo dentro de `unsafe_allow_html` sempre passa por `html.escape`.
- Ids de conversa passam pelo mesmo filtro de `storage._caminho_conversa` (nada sai da pasta historico/).
- Erros esperados: `storage.avisar(...)` mostra o aviso; exceções inesperadas vão para o log.
- Nada de dados pessoais no Git (nome, conversas, memória). O repo público começou de um snapshot limpo;
  nunca dar push do histórico local antigo (branch `historico-local`).

## Antes de terminar uma mudança
- `ruff check . && ruff format --check .`
- `python -m pytest`
- Mudou tela ou CSS: abrir o app e conferir no tema claro, no escuro e numa janela estreita.

## Como rodar
- `iAna.bat` (Windows) ou `streamlit run app.py`
