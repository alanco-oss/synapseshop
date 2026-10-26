"""Testes da redacao de PII/segredos (Aula 14)."""
from assist.redaction import redigir, redigir_logs


def test_redige_email_cpf_telefone_e_ip():
    texto = (
        "Contacto ana@dominio.com, cpf 123.456.789-00, "
        "tel (11) 99999-8888 e ip 192.168.0.1."
    )
    resultado = redigir(texto)
    assert "[REDIGIDO:email]" in resultado
    assert "[REDIGIDO:cpf]" in resultado
    assert "[REDIGIDO:telefone]" in resultado
    assert "[REDIGIDO:ip]" in resultado
    assert "ana@dominio.com" not in resultado
    assert "123.456.789-00" not in resultado
    assert "(11) 99999-8888" not in resultado
    assert "192.168.0.1" not in resultado


def test_redige_bearer_e_segredos_chave_valor():
    texto = (
        "Authorization: Bearer abcdEFGH1234-5678_9; "
        "api_key=MINHA_CHAVE_SUPER_SECRETA; senha=12345678"
    )
    resultado = redigir(texto)
    assert "[REDIGIDO:bearer]" in resultado
    assert "[REDIGIDO:segredo]" in resultado
    assert "Bearer abcdEFGH1234-5678_9" not in resultado
    assert "MINHA_CHAVE_SUPER_SECRETA" not in resultado
    assert "senha=12345678" not in resultado


def test_redige_lista_enumerada():
    logs = ["erro ao autenticar joao@empresa.com", "ip 10.0.0.5 falhou"]
    resultado = redigir_logs(logs)
    assert "1) erro ao autenticar " in resultado
    assert "2) ip " in resultado
    assert "joao@empresa.com" not in resultado
    assert "10.0.0.5" not in resultado
    assert "[REDIGIDO:email]" in resultado
    assert "[REDIGIDO:ip]" in resultado


def test_redige_string_simples():
    resultado = redigir_logs("token senha=12345678 e fim")
    assert "[REDIGIDO:segredo]" in resultado
    assert "senha=12345678" not in resultado


def test_redige_cartao_com_espacos():
    resultado = redigir("cartao 4111 1111 1111 1111 cobrado")
    assert "[REDIGIDO:cartao]" in resultado
    assert "4111 1111 1111 1111" not in resultado


def test_redige_cnpj():
    resultado = redigir("fornecedor 12.345.678/0001-95 aprovado")
    assert "[REDIGIDO:cnpj]" in resultado
    assert "12.345.678/0001-95" not in resultado
