"""Divisão de documentos em trechos e histórico enviado ao modelo (sem chamar o Ollama)."""

from iana import config
from iana.brain import _dividir_em_trechos
from iana.processor import _mensagem_valida, _montar_historico


def test_texto_curto_vira_um_trecho():
    assert _dividir_em_trechos("Um parágrafo só.") == ["Um parágrafo só."]


def test_trechos_respeitam_o_tamanho_e_nao_cortam_palavras():
    texto = "\n\n".join(f"Frase número {i} sobre um assunto qualquer." for i in range(200))
    trechos = _dividir_em_trechos(texto, tamanho=300, sobreposicao=60)
    assert len(trechos) > 1
    assert all(len(t) <= 300 for t in trechos)
    assert all(not t.startswith(("úmero", "rase")) for t in trechos)


def test_trechos_vizinhos_se_sobrepoem():
    texto = "\n\n".join(f"Parágrafo {i} com algum conteúdo." for i in range(40))
    a, b = _dividir_em_trechos(texto, tamanho=200, sobreposicao=80)[:2]
    assert a.splitlines()[-1] in b.splitlines()  # o fim de um trecho se repete no começo do próximo
    assert not b.startswith(a.splitlines()[0])


def test_respostas_de_erro_nao_voltam_para_o_modelo():
    assert not _mensagem_valida({"role": "assistant", "content": "⚠️ Ollama fora do ar"})
    assert not _mensagem_valida({"role": "assistant", "content": "(sem resposta)"})
    assert not _mensagem_valida({"role": "user", "content": "   "})
    assert _mensagem_valida({"role": "user", "content": "oi"})


def test_historico_comeca_sempre_por_uma_mensagem_da_pessoa():
    msgs = [{"role": "assistant", "content": "Oi!"}, {"role": "user", "content": "Tudo bem?"}]
    assert [m["role"] for m in _montar_historico(msgs, tem_img=False)] == ["user"]


def test_historico_respeita_o_limite_de_mensagens():
    msgs = []
    for i in range(50):
        msgs += [{"role": "user", "content": f"p{i}"}, {"role": "assistant", "content": f"r{i}"}]
    hist = _montar_historico(msgs, tem_img=False)
    assert len(hist) <= config.HISTORICO_MAX_MENSAGENS
    assert hist[-1]["content"] == "r49"


def test_imagem_antiga_vira_texto_quando_a_pergunta_nao_tem_imagem():
    msgs = [{"role": "user", "content": "veja", "imagens_b64": ["AAA"]}, {"role": "assistant", "content": "ok"}]
    hist = _montar_historico(msgs, tem_img=False)
    assert "images" not in hist[0]
    assert hist[0]["content"].startswith("[1 imagem enviada]")
