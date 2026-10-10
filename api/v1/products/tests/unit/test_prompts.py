"""Testes dos templates de prompt (Aula 14)."""
import pytest

from assist.prompts import MODO_EXPLAIN, MODO_SUMMARIZE, montar_mensagens


def test_montar_mensagens_summarize():
    mensagens = montar_mensagens(MODO_SUMMARIZE, "log 1")
    assert mensagens[0]["role"] == "system"
    assert "Resume" in mensagens[0]["content"]
    assert mensagens[1] == {
        "role": "user",
        "content": "Conteúdo do log (dados sensíveis já redigidos):\n\nlog 1",
    }


def test_montar_mensagens_explain():
    mensagens = montar_mensagens(MODO_EXPLAIN, "erro X")
    assert mensagens[0]["role"] == "system"
    assert "Explica" in mensagens[0]["content"]
    assert "erro X" in mensagens[1]["content"]


def test_modo_inexistente_falha_imediatamente():
    with pytest.raises(KeyError):
        montar_mensagens("traduzir", "log")