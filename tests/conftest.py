"""Os testes nunca tocam nas conversas e na memória de verdade: cada teste usa pastas temporárias."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iana import storage


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    historico, audio = tmp_path / "historico", tmp_path / "audio"
    historico.mkdir()
    audio.mkdir()
    monkeypatch.setattr(storage, "DIRETORIO_HISTORICO", str(historico))
    monkeypatch.setattr(storage, "DIRETORIO_AUDIO", str(audio))
    storage.listar_conversas_cached.clear()
    return historico, audio
