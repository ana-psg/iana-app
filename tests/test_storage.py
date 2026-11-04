"""Conversas salvas em disco: caminhos seguros, leitura e gravação."""

import pytest

from iana import storage


@pytest.mark.parametrize("id_ruim", ["", "!!!", "../", r"..\..", "   "])
def test_id_sem_caracteres_validos_e_recusado(pastas, id_ruim):
    with pytest.raises(ValueError):
        storage.carregar_conversa(id_ruim)


def test_id_com_barras_nao_sai_da_pasta(pastas):
    historico, _ = pastas
    caminho = storage._caminho_conversa("../../segredo")
    assert caminho.startswith(str(historico.resolve()))


def test_salvar_e_carregar_de_volta(pastas):
    msgs = [{"role": "user", "content": "Olá"}, {"role": "assistant", "content": "Oi!"}]
    storage.salvar_conversa("20261104_1200", msgs, nome="Teste", projeto="Casa", resumo="r")
    dados = storage.carregar_conversa("20261104_1200")
    assert dados == {"nome": "Teste", "projeto": "Casa", "resumo": "r", "mensagens": msgs}
    assert storage.listar_conversas() == ["20261104_1200"]


def test_conversa_que_nao_existe_vem_vazia(pastas):
    assert storage.carregar_conversa("20990101_0000")["mensagens"] == []


def test_formato_antigo_em_lista_ainda_abre(pastas):
    historico, _ = pastas
    (historico / "antiga.json").write_text('[{"role": "user", "content": "oi"}]', encoding="utf-8")
    dados = storage.carregar_conversa("antiga")
    assert dados["mensagens"][0]["content"] == "oi"
    assert dados["projeto"] == "Geral"


def test_arquivo_corrompido_nao_some_da_lista_e_avisa_quem_abre(pastas):
    historico, _ = pastas
    (historico / "quebrada.json").write_text("{nao é json", encoding="utf-8")
    assert storage.carregar_metadados_conversas(["quebrada"]) == {}
    with pytest.raises(ValueError):  # JSONDecodeError é um ValueError: o app.py mostra um aviso
        storage.carregar_conversa("quebrada")


def test_nome_de_exibicao():
    assert storage.obter_nome_exibicao({"nome": "Viagem"}, "x") == "Viagem"
    assert storage.obter_nome_exibicao({"mensagens": []}, "x") == "Nova conversa"
    assert storage.obter_nome_exibicao({"mensagens": [1]}, "20261104_1530") == "04/11 15:30"


def test_audio_so_dentro_da_pasta_de_audio(pastas):
    _, audio = pastas
    (audio / "resp.mp3").write_bytes(b"x")
    assert storage.caminho_audio("resp.mp3") == str(audio / "resp.mp3")
    assert storage.caminho_audio("../../resp.mp3") == str(audio / "resp.mp3")
    assert storage.caminho_audio(None) is None
