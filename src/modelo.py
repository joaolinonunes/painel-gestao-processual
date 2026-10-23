import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import ARQ_PROCESSADO, ARQ_AGRUPADO, ARQ_METRICAS

VARIAVEIS = ["dias_tramitacao", "qtd_movimentos", "dias_sem_movimento"]
K_ESCOLHIDO = 3
NOMES_GRUPOS = {
    3: ["Atenção baixa", "Atenção média", "Atenção alta"],
    4: ["Atenção baixa", "Atenção média", "Atenção alta", "Atenção muito alta"],
}


def preparar(df):
    X = df[VARIAVEIS].fillna(0).clip(lower=0)
    X = np.log1p(X)  # reduz o efeito de valores muito altos
    return StandardScaler().fit_transform(X)


def testar_k(X, ks=range(2, 7)):
    resultados = []
    for k in ks:
        modelo = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
        resultados.append({"k": k,
                           "inercia": float(modelo.inertia_),
                           "silhueta": float(silhouette_score(X, modelo.labels_))})
        print(f"K={k}  inércia={modelo.inertia_:.1f}  silhueta={resultados[-1]['silhueta']:.3f}")
    return resultados


def agrupar():
    df = pd.read_csv(ARQ_PROCESSADO, parse_dates=["data_ajuizamento", "data_ultimo_movimento"],
                     dtype={"numero_processo": str})  # texto: evita perder zeros à esquerda

    # O K-Means só olha os processos em andamento; os arquivados já terminaram
    ativos = df[~df["arquivado"]].copy()
    X = preparar(ativos)
    testes = testar_k(X)

    modelo = KMeans(n_clusters=K_ESCOLHIDO, n_init=10, random_state=42).fit(X)
    ativos["cluster"] = modelo.labels_

    # Ordena os grupos pelo "atraso": idade do processo + tempo sem movimento,
    # usando os centros do K-Means (já padronizados, então sem empates)
    idx = [VARIAVEIS.index("dias_tramitacao"), VARIAVEIS.index("dias_sem_movimento")]
    ordem = np.argsort(modelo.cluster_centers_[:, idx].sum(axis=1))
    nomes = NOMES_GRUPOS.get(K_ESCOLHIDO, [f"Grupo {i + 1}" for i in range(K_ESCOLHIDO)])
    ativos["grupo"] = ativos["cluster"].map(dict(zip(ordem, nomes)))

    # Ranking: 1 = processo que mais merece ser verificado.
    # Ordem: nível do grupo (alta antes de média antes de baixa) e, dentro do grupo,
    # índice de atenção (0 a 100) = média dos percentis de idade e de tempo sem movimento.
    ativos["nivel"] = ativos["grupo"].map({nome: i for i, nome in enumerate(nomes)})
    ativos["indice_atencao"] = (ativos[["dias_tramitacao", "dias_sem_movimento"]]
                                .rank(pct=True).mean(axis=1) * 100).round(1)
    ativos = ativos.sort_values(["nivel", "indice_atencao", "dias_sem_movimento"],
                                ascending=False)
    ativos["ranking"] = range(1, len(ativos) + 1)

    df["cluster"] = -1
    df["grupo"] = "Arquivado"
    df["indice_atencao"] = np.nan
    df["ranking"] = pd.array([pd.NA] * len(df), dtype="Int64")
    df.loc[ativos.index, "cluster"] = ativos["cluster"]
    df.loc[ativos.index, "grupo"] = ativos["grupo"]
    df.loc[ativos.index, "indice_atencao"] = ativos["indice_atencao"]
    df.loc[ativos.index, "ranking"] = ativos["ranking"].astype("Int64")

    resumo = ativos.groupby("grupo")[VARIAVEIS].agg(["mean", "median"]).round(1)
    print(resumo)

    metricas = {
        "k_escolhido": K_ESCOLHIDO,
        "processos_agrupados": int(len(ativos)),
        "processos_arquivados": int((df["grupo"] == "Arquivado").sum()),
        "silhueta": float(silhouette_score(X, modelo.labels_)),
        "testes_k": testes,
        "tamanho_grupos": df["grupo"].value_counts().to_dict(),
    }
    df.to_csv(ARQ_AGRUPADO, index=False)
    with open(ARQ_METRICAS, "w", encoding="utf-8") as arq:
        json.dump(metricas, arq, ensure_ascii=False, indent=2)
    print(f"Silhueta final: {metricas['silhueta']:.3f}")


if __name__ == "__main__":
    agrupar()
