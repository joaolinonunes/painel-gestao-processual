import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).resolve().parent
ARQ_AGRUPADO = BASE / "data" / "processed" / "processos_agrupados.csv"
ARQ_METRICAS = BASE / "data" / "processed" / "metricas_modelo.json"
ORDEM_GRUPOS = ["Atenção baixa", "Atenção média", "Atenção alta", "Atenção muito alta", "Arquivado"]
CORES = {"Atenção baixa": "#2e7d32", "Atenção média": "#f9a825", "Atenção alta": "#c62828", "Atenção muito alta": "#6a1b9a", "Arquivado": "#757575"}

st.set_page_config(page_title="Painel de Gestão Processual", page_icon="⚖️", layout="wide")


@st.cache_data
def carregar():
    df = pd.read_csv(ARQ_AGRUPADO, parse_dates=["data_ajuizamento", "data_ultimo_movimento"],
                     dtype={"numero_processo": str})
    # Recoloca zeros à esquerda e formata no padrão CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
    df["numero_processo"] = (df["numero_processo"].str.zfill(20)
                             .str.replace(r"^(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})$",
                                          r"\1-\2.\3.\4.\5.\6", regex=True))
    metricas = json.loads(ARQ_METRICAS.read_text(encoding="utf-8"))
    return df, metricas


df, metricas = carregar()
grupos = [g for g in ORDEM_GRUPOS if g in df["grupo"].unique()]

st.title("Painel de Apoio à Gestão Processual")
st.caption("Dados públicos da API do DataJud (CNJ). Ferramenta de apoio à gestão: "
           "as informações devem ser analisadas pelos profissionais responsáveis.")

# ---------- Filtros ----------
with st.sidebar:
    st.header("Filtros")
    classes = st.multiselect("Classe processual", sorted(df["classe"].dropna().unique()))
    orgaos = st.multiselect("Órgão julgador", sorted(df["orgao_julgador"].dropna().unique()))
    anos = st.slider("Ano de ajuizamento",
                     int(df["ano_ajuizamento"].min()), int(df["ano_ajuizamento"].max()),
                     (int(df["ano_ajuizamento"].min()), int(df["ano_ajuizamento"].max())))
    grupos_sel = st.multiselect("Grupo (K-Means)", grupos, default=grupos)
    situacao = st.radio("Situação", ["Todos", "Em andamento", "Arquivados"])

f = df[df["ano_ajuizamento"].between(*anos) & df["grupo"].isin(grupos_sel)]
if classes:
    f = f[f["classe"].isin(classes)]
if orgaos:
    f = f[f["orgao_julgador"].isin(orgaos)]
if situacao == "Em andamento":
    f = f[~f["arquivado"]]
elif situacao == "Arquivados":
    f = f[f["arquivado"]]

if f.empty:
    st.warning("Nenhum processo encontrado com os filtros selecionados.")
    st.stop()

# ---------- Indicadores ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Processos", f"{len(f):,}".replace(",", "."))
c2.metric("Tempo médio de tramitação", f"{f['dias_tramitacao'].mean():.0f} dias")
c3.metric("Em andamento", f"{(~f['arquivado']).sum():,}".replace(",", "."))
c4.metric("Em atenção alta", f"{(f['grupo'].isin(['Atenção alta', 'Atenção muito alta'])).sum():,}".replace(",", "."))

# ---------- Gráficos ----------
col_a, col_b = st.columns(2)

tempo_orgao = (f.groupby("orgao_julgador", as_index=False)["dias_tramitacao"].mean()
                 .sort_values("dias_tramitacao"))
col_a.plotly_chart(px.bar(tempo_orgao, x="dias_tramitacao", y="orgao_julgador", orientation="h",
                          title="Tempo médio de tramitação por órgão julgador",
                          labels={"dias_tramitacao": "Dias", "orgao_julgador": ""}),
                   width="stretch")

por_ano = f.groupby("ano_ajuizamento").size().reset_index(name="processos")
col_b.plotly_chart(px.line(por_ano, x="ano_ajuizamento", y="processos", markers=True,
                           title="Processos na amostra, por ano de ajuizamento",
                           labels={"ano_ajuizamento": "Ano", "processos": "Processos"}),
                   width="stretch")

col_c, col_d = st.columns(2)

por_grupo = f["grupo"].value_counts().reindex(grupos).dropna().reset_index()
por_grupo.columns = ["grupo", "processos"]
col_c.plotly_chart(px.bar(por_grupo, x="grupo", y="processos", color="grupo",
                          color_discrete_map=CORES, title="Processos por grupo",
                          labels={"grupo": "", "processos": "Processos"}),
                   width="stretch")

col_d.plotly_chart(px.scatter(f, x="qtd_movimentos", y="dias_tramitacao", color="grupo",
                              color_discrete_map=CORES, category_orders={"grupo": grupos},
                              opacity=0.6, title="Movimentações x tempo de tramitação",
                              labels={"qtd_movimentos": "Movimentações",
                                      "dias_tramitacao": "Dias de tramitação"}),
                   width="stretch")

# ---------- Processos parados ----------
st.subheader("Processos em andamento há mais tempo sem movimentação")
parados = (f[~f["arquivado"]]
           .sort_values("dias_sem_movimento", ascending=False)
           [["numero_processo", "classe", "orgao_julgador", "data_ajuizamento",
             "dias_tramitacao", "dias_sem_movimento", "grupo"]]
           .head(50))
st.dataframe(parados, hide_index=True, width="stretch",
             column_config={"numero_processo": "Processo", "classe": "Classe",
                            "orgao_julgador": "Órgão julgador",
                            "data_ajuizamento": st.column_config.DateColumn("Ajuizamento", format="DD/MM/YYYY"),
                            "dias_tramitacao": "Dias de tramitação",
                            "dias_sem_movimento": "Dias sem movimento", "grupo": "Grupo"})

# ---------- Sobre o modelo ----------
with st.expander("Sobre o modelo (K-Means)"):
    st.write(f"Número de grupos (K): **{metricas['k_escolhido']}** · "
             f"Coeficiente de silhueta: **{metricas['silhueta']:.3f}**")
    st.dataframe(pd.DataFrame(metricas["testes_k"]), hide_index=True)
    resumo = (f.groupby("grupo")[["dias_tramitacao", "qtd_movimentos", "dias_sem_movimento"]]
                .median().reindex(grupos).round(0))
    st.write("Mediana das variáveis em cada grupo:")
    st.dataframe(resumo)
