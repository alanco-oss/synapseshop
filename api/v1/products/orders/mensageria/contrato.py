"""Contrato estrutural do evento ``PedidoCriado`` (Aula 9).

O evento transporta os campos minimos de negocio mais a chave de idempotencia
(``idempotency_key``), derivada de uma chave de negocio (``pedido:{id}``) em
vez de um UUID aleatorio, para que a repeticao do mesmo facto de dominio
produza sempre a mesma chave de deduplicacao. ``event_id`` e um UUID por
mensagem e serve apenas para rastreio, nunca para dedupe.

Formato (JSON UTF-8 no topico ``pedidos.criado``)::

    {
      "event_id": "9f0c1e7e-...",
      "event_type": "PedidoCriado",
      "occurred_at": "2026-10-07T12:00:00+00:00",
      "idempotency_key": "pedido:42",
      "payload": {
        "pedido_id": 42,
        "user_id": 7,
        "total": "129.90",
        "status": "pending",
        "created_at": "2026-10-07T11:59:59+00:00"
      }
    }
"""
import uuid
from datetime import datetime, timezone

TIPO_EVENTO = "PedidoCriado"
CAMPOS_OBRIGATORIOS = (
    "event_id",
    "event_type",
    "occurred_at",
    "idempotency_key",
    "payload",
)
PAYLOAD_OBRIGATORIO = ("pedido_id", "user_id", "total", "status", "created_at")


def chave_idempotencia(pedido_id):
    """Chave de negocio usada como idempotency key do evento."""
    return f"pedido:{pedido_id}"


def construir_pedido_criado(pedido):
    """Monta o evento a partir de uma instancia persistida de ``Order``."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": TIPO_EVENTO,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": chave_idempotencia(pedido.pk),
        "payload": {
            "pedido_id": pedido.pk,
            "user_id": pedido.user_id,
            "total": str(pedido.total),
            "status": pedido.status,
            "created_at": pedido.created_at.isoformat(),
        },
    }


def validar(evento):
    """Valida o contrato minimo; levanta ``ValueError`` quando invalido."""
    if not isinstance(evento, dict):
        raise ValueError("evento nao e um objeto JSON")
    for campo in CAMPOS_OBRIGATORIOS:
        if not evento.get(campo):
            raise ValueError(f"campo obrigatorio em falta: {campo}")
    if evento["event_type"] != TIPO_EVENTO:
        raise ValueError(f"event_type desconhecido: {evento['event_type']}")
    payload = evento["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload nao e um objeto JSON")
    for campo in PAYLOAD_OBRIGATORIO:
        if payload.get(campo) is None:
            raise ValueError(f"campo obrigatorio em falta: payload.{campo}")
    return evento
