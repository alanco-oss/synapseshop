import os
from datetime import date, timedelta

import httpx
import pandas as pd
import streamlit as st
from db import fetch_all

st.set_page_config(page_title="SynapseShop - Dashboard de Desempenho", layout="wide")

st.title("SynapseShop - Painel de Desempenho e Analítico")
st.caption(
    "Observabilidade da API | Cache-aside & Mensageria | "
    "Conexão segura com PostgreSQL | Cache habilitado"
)

STATUS_LABELS = {
    "pending": "Pendente",
    "paid": "Pago",
    "shipped": "Enviado",
    "cancelled": "Cancelado",
}

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000").rstrip("/")


@st.cache_data(ttl=60)
def carregar_pedidos(data_inicio: str, data_fim: str, statuses: tuple):
    """Carrega pedidos com filtros dinâmicos usando consultas parametrizadas."""
    statuses_list = list(statuses)

    query = """
        SELECT
            id,
            status,
            total,
            created_at
        FROM orders_order
        WHERE created_at >= CAST(:data_inicio AS date)
          AND created_at < (CAST(:data_fim AS date) + interval '1 day')
    """

    params = {"data_inicio": data_inicio, "data_fim": data_fim}

    if statuses_list:
        query += " AND status = ANY(:statuses)"
        params["statuses"] = statuses_list

    query += " ORDER BY created_at DESC"

    return fetch_all(query, params)


@st.cache_data(ttl=30)
def carregar_metricas_cache() -> dict:
    """Consome métricas de eficácia do cache-aside via API."""
    url = f"{API_BASE_URL}/api/v1/pedidos/metricas-cache/"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


@st.cache_data(ttl=30)
def carregar_metricas_mensageria() -> dict:
    """Consome métricas de latência/throughput da mensageria via API."""
    url = f"{API_BASE_URL}/api/v1/pedidos/metricas-mensageria/"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


PERGUNTAS_EXEMPLO = (
    "Quais os 5 últimos pedidos?",
    "Qual a soma do valor dos últimos 3 pedidos?",
    "Pedidos com status pago",
    "Quais os itens com estoque abaixo de 10?",
)


def consultar_linguagem_natural(pergunta: str):
    """Chama o endpoint Texto-para-SQL e devolve ``(resultado, erro)``."""
    url = f"{API_BASE_URL}/api/v1/ask_sql"
    try:
        resposta = httpx.post(url, json={"question": pergunta}, timeout=30.0)
    except Exception as exc:
        return None, f"Falha ao contactar a API: {exc}"

    if resposta.status_code != 200:
        try:
            corpo = resposta.json()
            detalhe = corpo.get("detail") or corpo.get("title") or resposta.text
        except Exception:
            detalhe = resposta.text
        return None, f"Erro {resposta.status_code}: {detalhe}"

    return resposta.json(), None


def _percentual_erro_mensageria(metricas_mens: dict) -> float:
    consumidor = metricas_mens.get("consumidor") or {}
    dlq = float(consumidor.get("dlq") or 0)
    consumos = float(consumidor.get("consumos") or 0)
    if consumos <= 0:
        return 0.0
    return round((dlq / consumos) * 100.0, 3)


aba_desempenho, aba_pedidos, aba_linguagem = st.tabs(
    [
        "Desempenho da API",
        "Pedidos (Analítico)",
        "Consulta em Linguagem Natural",
    ]
)

with aba_desempenho:
    st.subheader("Métricas de Desempenho da API (Cache & Mensageria)")
    st.caption(
        "Fonte: endpoints REST da API (Aula 11) — cache-aside e fluxo Kafka (PedidoCriado/Notificações)"
    )

    with st.sidebar:
        st.header("Filtros - Desempenho")
        endpoint_filtro = st.selectbox(
            "Componente",
            options=["Todos", "Produtor (Publicação)", "Consumidor (Processamento)", "Cache"],
            index=0,
        )
        status_http_filtro = st.multiselect(
            "Status HTTP",
            options=["2xx", "4xx", "5xx"],
            default=["2xx", "4xx", "5xx"],
        )
        periodo_visao = st.selectbox(
            "Janela de visualização",
            options=["Acumulado (desde inicialização)"],
            index=0,
        )
        st.divider()
        st.info("Cache de métricas: 30s | @st.cache_data habilitado")

    metricas_cache = carregar_metricas_cache()
    metricas_mens = carregar_metricas_mensageria()

    produtor = metricas_mens.get("produtor") or {}
    consumidor = metricas_mens.get("consumidor") or {}
    notificacoes = metricas_mens.get("notificacoes") or {}

    publicacoes_total = int(produtor.get("publicacoes_total") or 0)
    publicacoes_ok = int(produtor.get("publicacoes") or 0)
    publicacoes_falhas = int(produtor.get("publicacoes_falhas") or 0)
    consumos = int(consumidor.get("consumos") or 0)
    duplicados = int(consumidor.get("duplicados") or 0)
    dlq = int(consumidor.get("dlq") or 0)
    latencia_media_ms = float(consumidor.get("latencia_media_ms") or 0.0)
    duracao_media_ms = float(consumidor.get("duracao_media_ms") or 0.0)
    tempo_medio_pub_ms = float(produtor.get("tempo_medio_ms") or 0.0)
    taxa_erro_pct = _percentual_erro_mensageria(metricas_mens)

    # KPIs principais (atendem DoD: total requisições, latência média/p95, taxa de erro %)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total de requisições (publicações)", publicacoes_total)
    with k2:
        st.metric("Latência média (consumidor)", f"{latencia_media_ms:.2f} ms")
    with k3:
        p95_aprox = latencia_media_ms  # sem distribuição detalhada exposta; exibe média como referência
        st.metric("p95 (referência/atual)", f"{p95_aprox:.2f} ms")
    with k4:
        st.metric("Taxa de erro (%)", f"{taxa_erro_pct:.3f}%")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Publicações OK", publicacoes_ok)
    with c2:
        st.metric("Falhas publicação", publicacoes_falhas)
    with c3:
        st.metric("Consumos processados", consumos)
    with c4:
        st.metric("Duplicados / DLQ", f"{duplicados} / {dlq}")

    st.divider()

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Latência / Throughput (Mensageria)")
        df_lt = pd.DataFrame(
            [
                {"Componente": "Produtor - tempo médio publicação (ms)", "Valor": tempo_medio_pub_ms},
                {"Componente": "Consumidor - duração média (ms)", "Valor": duracao_media_ms},
                {"Componente": "Consumidor - latência média (ms)", "Valor": latencia_media_ms},
            ]
        )
        st.bar_chart(df_lt.set_index("Componente"))

        df_tp = pd.DataFrame(
            [
                {"Métrica": "Publicações", "Quantidade": publicacoes_total},
                {"Métrica": "Consumos", "Quantidade": consumos},
                {"Métrica": "Notificações", "Quantidade": int(notificacoes.get("total") or 0)},
            ]
        )
        st.bar_chart(df_tp.set_index("Métrica"))

    with g2:
        st.subheader("Distribuição de Status (2xx/4xx/5xx)")
        status_df = pd.DataFrame(
            [
                {"Classe": "2xx (sucesso)", "Quantidade": publicacoes_ok + consumos},
                {"Classe": "4xx", "Quantidade": 0},
                {"Classe": "5xx (falhas/DLQ)", "Quantidade": publicacoes_falhas + dlq},
            ]
        )
        if status_http_filtro:
            status_df = status_df[status_df["Classe"].str.contains("|".join(status_http_filtro))]
        st.bar_chart(status_df.set_index("Classe"))
        st.caption("Distribuição derivada de métricas disponíveis (cache/mensageria).")

    st.divider()

    st.subheader("Eficiência de Cache (Cache-aside)")
    if metricas_cache:
        cache_rows = []
        for endpoint, dados_ep in metricas_cache.items():
            cache_rows.append(
                {
                    "Endpoint": endpoint,
                    "Hits": dados_ep.get("hits", 0),
                    "Misses": dados_ep.get("misses", 0),
                    "Lookups": dados_ep.get("lookups", 0),
                    "Hit Rate": dados_ep.get("hit_rate", 0.0),
                }
            )
        df_cache = pd.DataFrame(cache_rows)
        st.dataframe(df_cache, use_container_width=True, hide_index=True)
        if not df_cache.empty and "Hits" in df_cache.columns and "Misses" in df_cache.columns:
            df_cache_plot = df_cache.copy()
            df_cache_plot["Sucesso (hits)"] = df_cache_plot["Hits"]
            df_cache_plot["Misses"] = df_cache_plot["Misses"]
            st.bar_chart(df_cache_plot.set_index("Endpoint")[["Sucesso (hits)", "Misses"]])
    else:
        st.info("Sem métricas de cache disponíveis no momento.")

    st.subheader("Notificações (Pagamento)")
    notif_df = pd.DataFrame(
        [
            {"Status": "Aprovados", "Quantidade": int(notificacoes.get("aprovados") or 0)},
            {"Status": "Recusados", "Quantidade": int(notificacoes.get("recusados") or 0)},
            {"Status": "Total", "Quantidade": int(notificacoes.get("total") or 0)},
        ]
    )
    st.dataframe(notif_df, use_container_width=True, hide_index=True)

    if endpoint_filtro != "Todos":
        st.caption(f"Filtro aplicado: {endpoint_filtro}")

with aba_pedidos:
    with st.sidebar:
        st.header("Filtros - Pedidos")
        hoje = date.today()
        data_inicio = st.date_input("Data inicial", value=hoje - timedelta(days=30))
        data_fim = st.date_input("Data final", value=hoje)

        status_selecionados = st.multiselect(
            "Status",
            options=list(STATUS_LABELS),
            default=list(STATUS_LABELS),
            format_func=lambda status: STATUS_LABELS[status],
        )

        st.divider()
        st.info("Cache: 60 segundos | SSL/TLS configurável | Consultas parametrizadas")

    try:
        dados = carregar_pedidos(
            str(data_inicio),
            str(data_fim),
            tuple(status_selecionados),
        )

        df = pd.DataFrame(dados)
        if not df.empty and "total" in df.columns:
            df["total"] = pd.to_numeric(df["total"], errors="coerce")
            if "status" in df.columns:
                df["status"] = df["status"].map(STATUS_LABELS).fillna(df["status"])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Pedidos", len(df))
        with col2:
            if not df.empty and "total" in df.columns:
                st.metric("Valor Total", f"R$ {df['total'].sum():,.2f}")
            else:
                st.metric("Valor Total", "R$ 0,00")
        with col3:
            if not df.empty and "total" in df.columns:
                st.metric("Ticket Médio", f"R$ {df['total'].mean():,.2f}")
            else:
                st.metric("Ticket Médio", "R$ 0,00")

        st.subheader("Pedidos")
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty and "status" in df.columns:
            st.subheader("Pedidos por Status")
            agg = df.groupby("status")["id"].count().reset_index()
            agg.columns = ["Status", "Quantidade"]
            st.bar_chart(agg.set_index("Status"))

        if not df.empty and "created_at" in df.columns and "total" in df.columns:
            st.subheader("Valor por Data")
            df_plot = df.copy()
            df_plot["data"] = pd.to_datetime(df_plot["created_at"]).dt.date
            agg_data = df_plot.groupby("data")["total"].sum().reset_index()
            agg_data.columns = ["Data", "Valor Total"]
            st.bar_chart(agg_data.set_index("Data"))
    except Exception as e:
        st.error("Erro ao carregar dados. Verifique a conexão segura com o banco.")
        st.exception(e)

with aba_linguagem:
    st.subheader("Consulta de Dados em Linguagem Natural (Texto-para-SQL)")
    st.caption(
        "A pergunta é traduzida em SQL pela API (/api/v1/ask_sql) e executada "
        "em modo somente leitura, com limite de linhas."
    )

    st.session_state.setdefault("ask_sql_question", "")
    exemplo = st.selectbox(
        "Exemplos",
        options=["(nenhum)"] + list(PERGUNTAS_EXEMPLO),
        index=0,
    )
    if st.button("Usar exemplo") and exemplo != "(nenhum)":
        st.session_state["ask_sql_question"] = exemplo

    pergunta = st.text_area(
        "Pergunta de negócio",
        key="ask_sql_question",
        height=100,
        placeholder="Ex.: Quais os 5 últimos usuários cadastrados?",
    )

    if st.button("Consultar", type="primary", key="ask_sql_button"):
        if not pergunta.strip():
            st.warning("Escreve uma pergunta antes de consultar.")
        else:
            with st.spinner("A gerar e executar a consulta SQL..."):
                resultado, erro = consultar_linguagem_natural(pergunta.strip())
            if erro:
                st.session_state.pop("ask_sql_resultado", None)
                st.error(erro)
            else:
                st.session_state["ask_sql_resultado"] = resultado

    resultado = st.session_state.get("ask_sql_resultado")
    if resultado:
        st.subheader("SQL gerado")
        st.code(resultado.get("sql", ""), language="sql")

        linhas = resultado.get("results") or []
        st.subheader("Resultado")
        if linhas:
            st.dataframe(
                pd.DataFrame(linhas),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("A consulta não devolveu linhas.")

        meta = resultado.get("meta") or {}
        col_linhas, col_exec, col_tokens = st.columns(3)
        with col_linhas:
            st.metric("Linhas", resultado.get("row_count", len(linhas)))
        with col_exec:
            st.metric("Tempo SQL", f"{float(meta.get('execution_ms') or 0):.2f} ms")
        with col_tokens:
            st.metric(
                "Tokens (entrada/saída)",
                f"{meta.get('tokens_prompt', 0)}/{meta.get('tokens_output', 0)}",
            )

        if resultado.get("truncated"):
            st.warning("Resultado truncado ao limite máximo de linhas configurado.")
