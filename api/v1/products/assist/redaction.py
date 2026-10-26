"""Redacao de dados sensiveis (Aula 14).

Evita a fuga de Informacoes Pessoais Identificaveis (PII) e segredos antes de
qualquer conteudo seguir para o provedor de LLM ou para os logs de telemetria.
Os padroes cobrem os casos mais comuns em logs de aplicacoes: contactos,
documentos, pagamentos, redes e credenciais.
"""
import re

# (nome, padrao) -> o valor compilado substitui por ``[REDIGIDO:<nome>]``
# Padroes com chave (credenciais) primeiro: sao os mais especificos e evitam
# que numeros (senha/token) sejam apanhados como telefone/cartao.
PADROES = (
    (
        "bearer",
        re.compile(r"(?i)\bBearer[\s]+[A-Za-z0-9._\-]+"),
    ),
    (
        "segredo",
        re.compile(
            r"(?i)\b(?:api[_-]?key|apikey|secret|password|senha|token)"
            r"[\s]*[:=][\s]*[\"']?[A-Za-z0-9._\-/+]{4,}"
        ),
    ),
    (
        "email",
        re.compile(
            r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
        ),
    ),
    (
        "cpf",
        re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    ),
    (
        "cnpj",
        re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    ),
    (
        "cartao",
        # Antes do telefone: um cartao tem >= 13 digitos contiguos.
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    ),
    (
        "telefone",
        re.compile(
            r"\b(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{2,3}\)[\s.\-]?)?"
            r"\d{4,5}[\s.\-]?\d{4}\b"
        ),
    ),
    (
        "ip",
        re.compile(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
            r"|\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{0,4}\b"
        ),
    ),
)


def redigir(texto):
    """Substitui cada PII/segredo reconhecido por ``[REDIGIDO:<tipo>]``."""
    tabela = {padrao: f"[REDIGIDO:{nome}]" for nome, padrao in PADROES}
    for padrao, substituicao in tabela.items():
        texto = padrao.sub(substituicao, texto)
    return texto


def redigir_logs(logs):
    """Normaliza ``logs`` (string ou lista) e aplica a redacao.

    Listas viram texto enumerado (``1) linha``) para dar contexto ao modelo;
    o resultado nunca contem PII/segredos e e o unico conteudo que pode sair
    do processo.
    """
    if isinstance(logs, list):
        texto = "\n".join(
            f"{indice}) {linha}" for indice, linha in enumerate(logs, start=1)
        )
    else:
        texto = str(logs)
    return redigir(texto)
