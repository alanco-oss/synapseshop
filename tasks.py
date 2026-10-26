#!/usr/bin/env python
"""Comandos de operacao do SynapseShop (Onda 0 — rede de seguranca).

Antes: a suite so corria com ``cd api/v1/products && pytest`` e o lint
dependia de lembrar caminhos e de um ``npx`` avulso. Agora existe um comando
unico para cada operacao recorrente, que funciona igual em Windows, Linux e
macOS (ao contrario de um ``Makefile``, que exige ``make`` instalado).

    python tasks.py test        suite completa (nao precisa de Docker)
    python tasks.py lint        ruff + lint do contrato OpenAPI
    python tasks.py coverage    suite com relatorio HTML de cobertura
    python tasks.py check       verificacao completa antes do commit
    python tasks.py up / down   stack completo via docker compose
    python tasks.py --help      lista completa

Somente biblioteca padrao: nao ha nada a instalar para usar este ficheiro.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DJANGO = RAIZ / "api" / "v1" / "products"
VENV = RAIZ / ".venv"


def _python() -> str:
    """Interprete da venv do projeto (ou o Python do sistema, se nao existir)."""
    for candidato in (
        VENV / "Scripts" / "python.exe",
        VENV / "bin" / "python",
    ):
        if candidato.is_file():
            return str(candidato)
    return sys.executable


def _ajustar_windows(comando: list[str]) -> list[str]:
    """No Windows, executaveis ``.cmd``/``.bat`` (o ``npx`` e o ``docker``)
    nao podem ser lancados pelo ``CreateProcess``: tem de passar pelo
    interpretador de comandos."""
    if os.name != "nt" or not comando[0].lower().endswith((".cmd", ".bat")):
        return comando
    return [os.environ.get("COMSPEC", "cmd.exe"), "/c", *comando]


def _executar(comando: list[str], onde: Path | None = None) -> int:
    """Corre um comando e devolve o codigo de saida."""
    comando = _ajustar_windows(comando)
    print(f"\n$ {' '.join(comando)}\n")
    return subprocess.call(comando, cwd=str(onde or RAIZ))


def _pytest(extras: list[str]) -> int:
    return _executar([_python(), "-m", "pytest", *extras], onde=DJANGO)


def cmd_test(_: argparse.Namespace) -> int:
    """Suite de testes. Corre em SQLite em memoria: nao precisa de Docker."""
    return _pytest(["-q"])


def cmd_coverage(_: argparse.Namespace) -> int:
    """Suite de testes com relatorio de cobertura (terminal + HTML)."""
    return _pytest(["--cov-report=term-missing", "--cov-report=html"])


def cmd_ruff(_: argparse.Namespace) -> int:
    """Linter de Python."""
    return _executar([_python(), "-m", "ruff", "check", "."])


def cmd_spectral(_: argparse.Namespace) -> int:
    """Lint do contrato OpenAPI (docs/openapi.yaml)."""
    npx = shutil.which("npx")
    if npx is None:
        print("npx nao encontrado: instale Node.js para correr o lint do OpenAPI.")
        return 1
    return _executar(
        [npx, "--yes", "@stoplight/spectral-cli@6", "lint", "docs/openapi.yaml"]
    )


def cmd_lint(args: argparse.Namespace) -> int:
    """Todos os linters (ruff + Spectral)."""
    estado = cmd_ruff(args)
    return estado or cmd_spectral(args)


def cmd_check(args: argparse.Namespace) -> int:
    """Verificacao completa: linters + suite. E o que a CI corre."""
    estado = cmd_lint(args)
    return estado or cmd_test(args)


def cmd_up(_: argparse.Namespace) -> int:
    """Sobe o stack completo via docker compose."""
    estado = _executar(["docker", "compose", "up", "-d", "--build"])
    if estado == 0:
        _executar(["docker", "compose", "ps"])
    return estado


def cmd_down(_: argparse.Namespace) -> int:
    """Derruba o stack e remove os volumes."""
    return _executar(["docker", "compose", "down", "-v"])


def cmd_build(_: argparse.Namespace) -> int:
    """Constroi as imagens Docker sem as subir."""
    return _executar(["docker", "compose", "build"])


def cmd_clean(_: argparse.Namespace) -> int:
    """Remove caches e artefactos de build."""
    for alvo in (".pytest_cache", ".ruff_cache", "htmlcov", ".coverage"):
        caminho = RAIZ / alvo
        if caminho.is_dir():
            shutil.rmtree(caminho, ignore_errors=True)
        elif caminho.is_file():
            caminho.unlink(missing_ok=True)
    for cache in RAIZ.rglob("__pycache__"):
        if VENV not in cache.parents:
            shutil.rmtree(cache, ignore_errors=True)
    print("Artefactos removidos.")
    return 0


COMANDOS = {
    "test": cmd_test,
    "coverage": cmd_coverage,
    "ruff": cmd_ruff,
    "spectral": cmd_spectral,
    "lint": cmd_lint,
    "check": cmd_check,
    "up": cmd_up,
    "down": cmd_down,
    "build": cmd_build,
    "clean": cmd_clean,
}


def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Comandos de operacao do SynapseShop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    analizador.add_argument(
        "comando",
        choices=sorted(COMANDOS),
        help="operacao a executar",
    )
    args = analizador.parse_args(argumentos)
    return COMANDOS[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
