"""Circuit breaker do ``llm_service`` (Aula 14).

Estado em memória por processo (com 2 workers gunicorn síncronos é suficiente)
com o ciclo ``closed -> open -> half-open -> closed``:

- **closed**: pedidos fluem; ``falhas_consecutivas`` chegando ao limiar abre;
- **open**: pedidos são recusados sem chegar ao provedor (``permitir()``
  devolve ``False``) durante a cooldown;
- **half-open**: após a cooldown, deixa passar um pedido de teste; sucesso
  fecha, falha reabre (e volta à cooldown).

O relógio é injetável (``time.monotonic``) para os testes poderem avançar o
tempo de forma determinística.
"""
import logging
import threading
import time

from . import config as _config

logger = logging.getLogger("assist")

ESTADO_FECHADO = "closed"
ESTADO_ABERTO = "open"
ESTADO_SEMI_ABERTO = "half_open"


class Interruptor:
    def __init__(
        self,
        falhas_para_abrir,
        timeout_aberto,
        relogio=time.monotonic,
    ):
        self.falhas_para_abrir = falhas_para_abrir
        self.timeout_aberto = timeout_aberto
        self._relogio = relogio
        self._estado = ESTADO_FECHADO
        self._falhas = 0
        self._aberto_desde = 0.0
        self._lock = threading.Lock()

    @property
    def estado(self):
        with self._lock:
            if (
                self._estado == ESTADO_ABERTO
                and self._relogio() - self._aberto_desde >= self.timeout_aberto
            ):
                return ESTADO_SEMI_ABERTO
            return self._estado

    def permitir(self):
        return self.estado != ESTADO_ABERTO

    def registrar_sucesso(self):
        with self._lock:
            self._falhas = 0
            if self._estado in (ESTADO_SEMI_ABERTO, ESTADO_ABERTO):
                logger.info(
                    "acao=interruptor estado_anterior=%s estado=closed",
                    self._estado,
                )
            self._estado = ESTADO_FECHADO

    def registrar_falha(self):
        with self._lock:
            if self._estado in (ESTADO_SEMI_ABERTO, ESTADO_ABERTO):
                # Falhou no teste do half-open: volta a abrir e reinicia a cooldown.
                self._estado = ESTADO_ABERTO
                self._aberto_desde = self._relogio()
                logger.warning(
                    "acao=interruptor estado_anterior=%s estado=open",
                    ESTADO_SEMI_ABERTO,
                )
                return
            self._falhas += 1
            if self._falhas >= self.falhas_para_abrir:
                self._estado = ESTADO_ABERTO
                self._aberto_desde = self._relogio()
                logger.warning(
                    "acao=interruptor estado=open falhas=%d",
                    self._falhas,
                )

    def resetar(self):
        with self._lock:
            self._estado = ESTADO_FECHADO
            self._falhas = 0
            self._aberto_desde = 0.0


INTERRUPTOR = Interruptor(
    falhas_para_abrir=_config.LLM_CIRCUIT_FALHAS_PARA_ABRIR,
    timeout_aberto=_config.LLM_CIRCUIT_TIMEOUT_ABERTO,
)