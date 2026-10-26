from datetime import date, timedelta

import pandas as pd
import streamlit as st
from db import fetch_all

st.set_page_config(page_title="SynapseShop - Dashboard", layout="wide")

st.title("SynapseShop - Painel Analítico")
st.caption("Conexão segura com PostgreSQL | Consultas parametrizadas | Cache habilitado")

STATUS_LABELS = {
    "pending": "Pendente",
    "paid": "Pago",
    "shipped": "Enviado",
    "cancelled": "Cancelado",
}


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


with st.sidebar:
    st.header("Filtros")
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
        if not df.empty:
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
