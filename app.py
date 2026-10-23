import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path(__file__).resolve().parent
ARQ_AGRUPADO = BASE / "data" / "processed" / "processos_agrupados.csv"
ARQ_METRICAS = BASE / "data" / "processed" / "metricas_modelo.json"
ARQ_COMPARACAO = BASE / "data" / "processed" / "comparacao_regra.csv"

# Do maior para o menor nível de atenção (posição 1 do ranking = topo)
ORDEM_GRUPOS = ["Atenção muito alta", "Atenção alta", "Atenção média", "Atenção baixa", "Arquivado"]
CORES = {"Atenção muito alta": "#6a1b9a", "Atenção alta": "#c62828", "Atenção média": "#ef8f00",
         "Atenção baixa": "#2e7d32", "Arquivado": "#757575"}
MARCA = {"Atenção muito alta": "🟣", "Atenção alta": "🔴", "Atenção média": "🟠",
         "Atenção baixa": "🟢", "Arquivado": "⚪"}
EXPLICACAO = {
    "Atenção muito alta": "Prioridade máxima de verificação.",
    "Atenção alta": "Maior prioridade de verificação: processos antigos e sem andamento há muito tempo.",
    "Atenção média": "Prioridade intermediária.",
    "Atenção baixa": "Menor prioridade: processos mais recentes.",
    "Arquivado": "Já encerrados, por isso ficam fora do ranking.",
}

st.set_page_config(page_title="Painel de Gestão Processual", page_icon="⚖️", layout="wide",
                   initial_sidebar_state="auto")

st.markdown("""
<style>
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem;margin:.25rem 0 1rem}
@media (min-width:900px){.kpis{grid-template-columns:repeat(4,1fr)}}
.kpi{border:1px solid rgba(128,128,128,.35);border-radius:8px;padding:.6rem .8rem}
.kpi-valor{font-size:1.6rem;font-weight:700;line-height:1.2}
.kpi-nome{font-size:.85rem;opacity:.75}
@media (max-width:640px){
  [data-testid="stMainBlockContainer"], .block-container{padding:3.5rem .8rem 3rem !important}
  h1{font-size:1.5rem !important}
}
</style>
""", unsafe_allow_html=True)


# ---------- Dados ----------
def encurtar(nome):
    if not isinstance(nome, str):
        return "Não informado"
    curto = re.sub(r"\s*(da comarca\s+)?d[eo]\s+s[aã]o\s+jos[eé]\s+do\s+rio\s+preto\s*$", "",
                   nome, flags=re.I).strip(" -").title()
    return curto if len(curto) <= 32 else curto[:31] + "…"


@st.cache_data
def carregar():
    df = pd.read_csv(ARQ_AGRUPADO, parse_dates=["data_ajuizamento", "data_ultimo_movimento"],
                     dtype={"numero_processo": str})
    df["numero_raw"] = df["numero_processo"].str.zfill(20)
    # Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
    df["numero_processo"] = df["numero_raw"].str.replace(
        r"^(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})$", r"\1-\2.\3.\4.\5.\6", regex=True)
    df["ranking"] = df["ranking"].astype("Int64")
    df["vara"] = df["orgao_julgador"].map(encurtar)
    metricas = json.loads(ARQ_METRICAS.read_text(encoding="utf-8"))
    comparacao = pd.read_csv(ARQ_COMPARACAO) if ARQ_COMPARACAO.exists() else None
    return df, metricas, comparacao


def fmt(n):
    return f"{n:,.0f}".replace(",", ".")


df, metricas, comparacao = carregar()
total_ativos = int(df["ranking"].notna().sum())
ativos_df = df[df["ranking"].notna()]
medianas = df.groupby("grupo")[["dias_sem_movimento", "dias_tramitacao", "qtd_movimentos"]].median()
grupos = [g for g in ORDEM_GRUPOS if g in df["grupo"].unique()]


# ---------- Processos acompanhados (a lista fica no endereço da página) ----------
def ler_seguindo():
    bruto = st.query_params.get("seguindo", "")
    validos = set(df["numero_raw"])
    return [n for n in bruto.split(",") if n in validos]


if "seguindo" not in st.session_state:
    st.session_state.seguindo = ler_seguindo()


def alternar(numero_raw):
    lista = st.session_state.seguindo
    if numero_raw in lista:
        lista.remove(numero_raw)
    else:
        lista.append(numero_raw)
    if lista:
        st.query_params["seguindo"] = ",".join(lista)
    elif "seguindo" in st.query_params:
        del st.query_params["seguindo"]


def cartao(linha, prefixo):
    seguindo = linha.numero_raw in st.session_state.seguindo
    with st.container(border=True):
        st.markdown(f"**{linha.numero_processo}**")
        if pd.notna(linha.ranking):
            posicao = f"posição {linha.ranking} de {total_ativos} no ranking"
        else:
            posicao = "arquivado, sem posição no ranking"
        st.markdown(f"{MARCA.get(linha.grupo, '')} **{linha.grupo}**, {posicao}")
        detalhes = [linha.vara,
                    f"{fmt(linha.dias_sem_movimento)} dias sem movimento",
                    f"{fmt(linha.dias_tramitacao)} dias de tramitação",
                    f"{fmt(linha.qtd_movimentos)} movimentos"]
        if pd.notna(linha.indice_atencao):
            detalhes.append(f"índice de atenção {str(linha.indice_atencao).replace('.', ',')}")
            detalhes.append(f"mediana do grupo: {fmt(medianas.loc[linha.grupo, 'dias_sem_movimento'])} "
                            "dias sem movimento")
        st.caption("; ".join(detalhes))
        st.button("★ Acompanhando (tocar para remover)" if seguindo else "☆ Acompanhar este processo",
                  key=f"{prefixo}_{linha.numero_raw}", on_click=alternar, args=(linha.numero_raw,),
                  type="secondary" if seguindo else "primary")


# ---------- Cabeçalho ----------
st.title("Painel de apoio à gestão processual")
st.caption("Dados públicos do DataJud (CNJ). O painel só aponta processos para verificação; "
           "a decisão é sempre do profissional responsável.")

# ---------- Busca ----------
busca = st.text_input("Buscar processo", placeholder="Digite 4 ou mais números do processo")
digitos = re.sub(r"\D", "", busca)
if digitos:
    if len(digitos) < 4:
        st.caption("Digite pelo menos 4 números.")
    else:
        achados = df[df["numero_raw"].str.contains(digitos, regex=False)].sort_values("ranking")
        if achados.empty:
            st.info("Nenhum processo encontrado. Este painel só tem os processos da amostra coletada.")
        else:
            if len(achados) > 5:
                st.caption(f"{len(achados)} processos encontrados. Mostrando os 5 primeiros; "
                           "digite mais números para refinar.")
            for linha in achados.head(5).itertuples():
                cartao(linha, "busca")

# ---------- Meus processos ----------
st.subheader("Processos que acompanho")
if st.session_state.seguindo:
    meus = (df[df["numero_raw"].isin(st.session_state.seguindo)]
            .sort_values("ranking", na_position="last"))
    for linha in meus.itertuples():
        cartao(linha, "meu")
    st.caption("Para guardar esta lista, salve o endereço desta página nos favoritos do navegador.")
else:
    st.caption("Nenhum processo marcado. Busque um número acima e toque em Acompanhar.")

# ---------- Filtros (menu lateral) ----------
ano_min, ano_max = int(df["ano_ajuizamento"].min()), int(df["ano_ajuizamento"].max())
with st.sidebar:
    st.header("Filtros")
    varas = st.multiselect("Vara", sorted(df["vara"].unique()))
    classes = []
    if df["classe"].nunique() > 1:
        classes = st.multiselect("Classe processual", sorted(df["classe"].dropna().unique()))
    anos = st.slider("Ano de ajuizamento", ano_min, ano_max, (ano_min, ano_max)) \
        if ano_min < ano_max else (ano_min, ano_max)
    grupos_sel = st.multiselect("Grupo", grupos, default=grupos)
    situacao = st.radio("Situação", ["Todos", "Em andamento", "Arquivados"])

f = df[df["ano_ajuizamento"].between(*anos) & df["grupo"].isin(grupos_sel)]
if varas:
    f = f[f["vara"].isin(varas)]
if classes:
    f = f[f["classe"].isin(classes)]
if situacao == "Em andamento":
    f = f[~f["arquivado"]]
elif situacao == "Arquivados":
    f = f[f["arquivado"]]

if f.empty:
    st.warning("Nenhum processo com os filtros escolhidos. Amplie a seleção nos filtros do menu lateral.")
    st.stop()

# ---------- Indicadores ----------
ativos_filtro = []
if varas:
    ativos_filtro.append("vara " + ", ".join(varas))
if classes:
    ativos_filtro.append("classe " + ", ".join(classes))
if anos != (ano_min, ano_max):
    ativos_filtro.append(f"ajuizados de {anos[0]} a {anos[1]}")
if len(grupos_sel) != len(grupos):
    ativos_filtro.append("grupos " + ", ".join(grupos_sel))
if situacao != "Todos":
    ativos_filtro.append(situacao.lower())
st.caption("Filtros ativos: " + "; ".join(ativos_filtro) + "." if ativos_filtro else
           "Mostrando todos os processos da amostra. Os filtros ficam no menu lateral "
           "(no celular, toque na seta no canto superior esquerdo).")

em_andamento = f[~f["arquivado"]]
maior_parado = fmt(em_andamento["dias_sem_movimento"].max()) + " dias" if len(em_andamento) else "sem dados"
indicadores = [
    ("Processos na amostra", fmt(len(f))),
    ("Em andamento", fmt(len(em_andamento))),
    ("Em atenção alta", fmt(f["grupo"].isin(["Atenção alta", "Atenção muito alta"]).sum())),
    ("Maior tempo sem movimento", maior_parado),
]
st.markdown('<div class="kpis">' + "".join(
    f'<div class="kpi"><div class="kpi-valor">{valor}</div><div class="kpi-nome">{nome}</div></div>'
    for nome, valor in indicadores) + "</div>", unsafe_allow_html=True)

# ---------- Ranking ----------
st.subheader("Ranking de atenção")
st.caption("A posição 1 é o processo que mais merece ser verificado. A ordem considera o grupo e, "
           "dentro de cada grupo, o índice de atenção (0 a 100), que combina o tempo de tramitação "
           "e o tempo sem movimento. Toque em uma linha para ver o processo e acompanhá-lo. "
           "No celular, deslize a tabela para o lado para ver as demais colunas.")
st.caption("Legenda: 🔴 atenção alta, 🟠 média, 🟢 baixa, ★ processo que você acompanha.")
quantos = st.radio("Mostrar", ["20", "50", "100", "Todos"], horizontal=True)

ranking = f[f["ranking"].notna()].sort_values("ranking")
if quantos != "Todos":
    ranking = ranking.head(int(quantos))

if ranking.empty:
    st.info("Processos arquivados não entram no ranking. Escolha Todos ou Em andamento nos filtros.")
else:
    seguidos = ranking["numero_raw"].isin(st.session_state.seguindo)
    exibir = pd.DataFrame({
        "#": ranking["ranking"].astype(int),
        "Grupo": [MARCA.get(g, "") + ("★" if seg else "")
                  for g, seg in zip(ranking["grupo"], seguidos)],
        "Processo": ranking["numero_processo"],
        "Dias sem movimento": ranking["dias_sem_movimento"].astype(int),
        "Dias de tramitação": ranking["dias_tramitacao"].astype(int),
        "Ajuizamento": ranking["data_ajuizamento"],
        "Classe": ranking["classe"],
        "Órgão julgador": ranking["orgao_julgador"],
    })

    def realcar(linha):
        estilo = "background-color: rgba(255, 193, 7, 0.30); font-weight: 600" if "★" in linha["Grupo"] else ""
        return [estilo] * len(linha)

    evento = st.dataframe(
        exibir.style.apply(realcar, axis=1), hide_index=True, width="stretch",
        height=min(40 + 35 * len(exibir), 460), key="tabela_ranking",
        on_select="rerun", selection_mode="single-row",
        column_config={
            "#": st.column_config.NumberColumn(width=50, pinned=True),
            "Grupo": st.column_config.TextColumn(width=62, pinned=True),
            "Processo": st.column_config.TextColumn(width=185),
            "Dias sem movimento": st.column_config.NumberColumn(width=150),
            "Dias de tramitação": st.column_config.NumberColumn(width=150),
            "Ajuizamento": st.column_config.DateColumn(format="DD/MM/YYYY", width=105),
            "Classe": st.column_config.TextColumn(width=250),
            "Órgão julgador": st.column_config.TextColumn(width=330)})
    escolhidas = evento.selection.rows
    if escolhidas:
        cartao(ranking.iloc[escolhidas[0]], "tabela")

# ---------- Grupos ----------
CONFIG_GRAFICO = {"displayModeBar": False, "scrollZoom": False}
st.subheader("Como os processos se dividem")
contagem = f["grupo"].value_counts().reindex(grupos).dropna().astype(int).reset_index()
contagem.columns = ["Grupo", "Processos"]
fig = px.bar(contagem, x="Processos", y="Grupo", orientation="h", color="Grupo",
             color_discrete_map=CORES, text="Processos")
fig.update_traces(textposition="outside", cliponaxis=False)
fig.update_yaxes(categoryorder="array", categoryarray=grupos[::-1], title=None)
fig.update_xaxes(title=None, visible=False)
fig.update_layout(showlegend=False, height=60 + 50 * len(contagem), dragmode=False,
                  margin=dict(l=0, r=30, t=10, b=0), font=dict(size=14))
st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)
for g in grupos:
    st.markdown(f"{MARCA[g]} **{g}**: {EXPLICACAO[g]}")

# ---------- Ajuizamento por ano ----------
st.subheader("Quando os processos foram ajuizados")
st.caption("A coleta limitou o número de processos por trimestre, então este gráfico mostra a "
           "amostra e não o volume real da comarca.")
por_ano = f.groupby("ano_ajuizamento").size().reset_index(name="Processos")
fig = px.line(por_ano, x="ano_ajuizamento", y="Processos", markers=True, text="Processos")
fig.update_traces(textposition="top center", line_color="#1F5F8B", marker=dict(size=8))
fig.update_xaxes(type="category", title=None)
fig.update_yaxes(visible=False, range=[0, por_ano["Processos"].max() * 1.25])
fig.update_layout(height=300, dragmode=False, margin=dict(l=0, r=10, t=10, b=0), font=dict(size=13))
st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)

# ---------- Por vara ----------
if f["orgao_julgador"].nunique() > 1:
    st.subheader("Tempo de tramitação por vara")
    st.caption("Média em dias. Inclui processos arquivados (duração total) e em andamento (idade).")
    por_vara = (f.groupby(["orgao_julgador", "vara"], as_index=False)["dias_tramitacao"].mean()
                  .round(0).sort_values("dias_tramitacao", ascending=False))
    fig = px.bar(por_vara, x="dias_tramitacao", y="vara", orientation="h", text="dias_tramitacao",
                 hover_name="orgao_julgador")
    fig.update_traces(textposition="outside", cliponaxis=False, marker_color="#1F5F8B")
    fig.update_yaxes(categoryorder="array", categoryarray=list(por_vara["vara"])[::-1],
                     title=None, automargin=True)
    fig.update_xaxes(visible=False)
    fig.update_layout(height=60 + 50 * len(por_vara), dragmode=False,
                      margin=dict(l=0, r=40, t=10, b=0), font=dict(size=13))
    st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)

# ---------- O que a IA fez ----------
st.subheader("O que a IA fez")
st.write("A IA (algoritmo K-Means) olhou três medidas de cada processo em andamento: dias de "
         "tramitação, número de movimentos e dias sem movimento. Sem receber nenhuma regra pronta, "
         "ela juntou os processos que se parecem entre si. Os grupos de atenção vêm desse agrupamento.")
st.caption("Esta seção usa todos os processos em andamento, sem aplicar os filtros.")

grupos_ativos = [g for g in grupos if g != "Arquivado"]
aba1, aba2, aba3, aba4 = st.tabs(["Perfil dos grupos", "Mapa dos processos", "Nº de grupos",
                                  "IA x regra simples"])

with aba1:
    st.write("Cada gráfico mostra o valor típico (mediana) de uma medida em cada grupo. "
             "Compare o grupo de atenção alta com os demais.")
    perfil = ativos_df.groupby("grupo")[["dias_sem_movimento", "dias_tramitacao", "qtd_movimentos"]] \
        .median().reindex(grupos_ativos)
    medidas = [("dias_sem_movimento", "Dias sem movimento"), ("dias_tramitacao", "Dias de tramitação"),
               ("qtd_movimentos", "Número de movimentos")]
    for coluna, (campo, titulo) in zip(st.columns(3), medidas):
        dados = perfil[campo].reset_index()
        dados.columns = ["Grupo", "Valor"]
        fig = px.bar(dados, x="Valor", y="Grupo", orientation="h", color="Grupo",
                     color_discrete_map=CORES, text=dados["Valor"].round(0).astype(int).map(fmt))
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_yaxes(categoryorder="array", categoryarray=grupos_ativos[::-1], title=None)
        fig.update_xaxes(visible=False, range=[0, max(dados["Valor"].max() * 1.35, 1)])
        fig.update_layout(showlegend=False, height=60 + 55 * len(dados), dragmode=False,
                          margin=dict(l=0, r=10, t=5, b=0), font=dict(size=13))
        coluna.markdown(f"**{titulo}**")
        coluna.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO, key=f"perfil_{campo}")

with aba2:
    st.write("Cada ponto é um processo em andamento. Os processos do mesmo grupo ficam próximos. "
             "Quanto mais para cima e para a direita, mais antigo e mais tempo sem andamento. "
             "O X preto marca o valor típico de cada grupo.")
    fig = px.scatter(ativos_df, x="dias_sem_movimento", y="dias_tramitacao", color="grupo",
                     color_discrete_map=CORES, category_orders={"grupo": grupos_ativos}, opacity=0.7,
                     labels={"dias_sem_movimento": "Dias sem movimento",
                             "dias_tramitacao": "Dias de tramitação", "grupo": "Grupo"})
    fig.update_traces(marker=dict(size=8))
    centros = ativos_df.groupby("grupo")[["dias_sem_movimento", "dias_tramitacao"]].median()
    fig.add_trace(go.Scatter(
        x=centros["dias_sem_movimento"], y=centros["dias_tramitacao"], mode="markers",
        marker=dict(symbol="x", size=14, color="black", line=dict(width=2)),
        name="Valor típico do grupo", hovertext=list(centros.index), hoverinfo="text"))
    seguidos_mapa = ativos_df[ativos_df["numero_raw"].isin(st.session_state.seguindo)]
    if not seguidos_mapa.empty:
        fig.add_trace(go.Scatter(
            x=seguidos_mapa["dias_sem_movimento"], y=seguidos_mapa["dias_tramitacao"], mode="markers",
            marker=dict(symbol="star", size=17, color="#FFC107", line=dict(color="black", width=1)),
            name="Processos que acompanho", hovertext=seguidos_mapa["numero_processo"],
            hoverinfo="text"))
    fig.update_layout(height=470, dragmode=False, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=-0.3, title=None), font=dict(size=13))
    st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)

with aba3:
    st.write("A IA testou de 2 a 6 grupos. A silhueta mede o quanto os grupos ficam separados "
             "entre si: quanto maior, melhor. O número com a maior silhueta foi o escolhido.")
    testes = pd.DataFrame(metricas["testes_k"])
    testes["Escolha"] = np.where(testes["k"] == metricas["k_escolhido"], "Escolhido", "Testado")
    fig = px.bar(testes, x="k", y="silhueta", color="Escolha",
                 color_discrete_map={"Escolhido": "#1F5F8B", "Testado": "#9aa5b1"},
                 text=testes["silhueta"].map(lambda v: f"{v:.3f}".replace(".", ",")),
                 labels={"k": "Número de grupos", "silhueta": "Silhueta"})
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(type="category")
    fig.update_yaxes(visible=False, range=[0, max(testes["silhueta"].max() * 1.25, 0.1)])
    fig.update_layout(height=320, dragmode=False, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=-0.28, title=None), font=dict(size=13))
    st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)
    melhor_k = int(testes.sort_values("silhueta", ascending=False).iloc[0]["k"])
    st.caption(f"Silhueta do agrupamento final: {str(round(metricas['silhueta'], 3)).replace('.', ',')}. "
               "Acima de 0,5 indica grupos bem separados."
               + ("" if melhor_k == metricas["k_escolhido"] else
                  f" Atenção: o maior valor foi com {melhor_k} grupos."))

with aba4:
    st.write("Uma regra simples marca como parado todo processo com mais de X dias sem movimento. "
             "O gráfico mostra, para cada valor de X, quantos processos a regra e a IA marcam em "
             "comum e quantos só um dos dois marca.")
    if comparacao is None:
        st.info("A comparação ainda não foi gerada. Rode python src/comparar_regra.py e atualize a página.")
    else:
        rotulo = comparacao["corte_dias_sem_movimento"].map(lambda c: f"{fmt(c)} dias")
        fig = go.Figure()
        limite_rotulo = 0.08 * comparacao[["em_comum", "so_regra", "so_kmeans"]].sum(axis=1).max()
        for campo, nome, cor in [("em_comum", "Os dois marcam", "#1F5F8B"),
                                 ("so_regra", "Só a regra marca", "#ef8f00"),
                                 ("so_kmeans", "Só a IA marca", "#00897b")]:
            fig.add_trace(go.Bar(x=rotulo, y=comparacao[campo], name=nome, marker_color=cor,
                                 text=[str(v) if v >= limite_rotulo else "" for v in comparacao[campo]],
                                 textposition="inside"))
        fig.update_layout(barmode="stack", height=360, dragmode=False,
                          margin=dict(l=0, r=0, t=10, b=0), font=dict(size=13),
                          legend=dict(orientation="h", y=-0.25, title=None),
                          xaxis_title="Regra: mais de X dias sem movimento", yaxis_title="Processos")
        st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)
        melhor = comparacao.sort_values("sobreposicao_pct", ascending=False).iloc[0]
        st.caption(f"O corte de {fmt(melhor['corte_dias_sem_movimento'])} dias foi o de maior concordância "
                   f"({str(melhor['sobreposicao_pct']).replace('.', ',')}%), mas ele foi escolhido depois de ver "
                   "os resultados. A IA encontra o limite sozinha, a partir dos dados.")
