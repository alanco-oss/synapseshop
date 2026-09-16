FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt \
    && mkdir -p /root/.local


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --create-home app

WORKDIR /app

COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["python", "app.py"]