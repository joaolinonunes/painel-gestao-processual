"""Compara o K-Means com uma regra simples: "mais de X dias sem movimento".

Não existe resposta certa para dizer qual processo está de fato parado, então a
comparação mede o quanto os dois métodos concordam e onde eles divergem.
"""
import pandas as pd

from config import ARQ_AGRUPADO

CORTES = [180, 365, 730, 1000, 1095]  # dias sem movimento
GRUPOS_ALTA = ["Atenção alta", "Atenção muito alta"]
ARQ_SAIDA = ARQ_AGRUPADO.parent / "comparacao_regra.csv"

df = pd.read_csv(ARQ_AGRUPADO, dtype={"numero_processo": str})
ativos = df[df["grupo"] != "Arquivado"].copy()
alta = ativos["grupo"].isin(GRUPOS_ALTA)

print(f"Processos em andamento: {len(ativos)}")
print(f"Marcados pelo K-Means (grupos de atenção alta): {int(alta.sum())}")
print(f"Menor tempo sem movimento no grupo de atenção alta: "
      f"{int(ativos.loc[alta, 'dias_sem_movimento'].min())} dias")
print(f"Mediana no grupo de atenção alta: "
      f"{int(ativos.loc[alta, 'dias_sem_movimento'].median())} dias\n")

linhas = []
for corte in CORTES:
    regra = ativos["dias_sem_movimento"] > corte
    em_comum = int((regra & alta).sum())
    so_regra = int((regra & ~alta).sum())
    so_kmeans = int((~regra & alta).sum())
    uniao = em_comum + so_regra + so_kmeans
    linhas.append({
        "corte_dias_sem_movimento": corte,
        "marcados_pela_regra": int(regra.sum()),
        "marcados_pelo_kmeans": int(alta.sum()),
        "em_comum": em_comum,
        "so_regra": so_regra,
        "so_kmeans": so_kmeans,
        "sobreposicao_pct": round(100 * em_comum / uniao, 1) if uniao else 0.0,
    })

tabela = pd.DataFrame(linhas)
print(tabela.to_string(index=False))
tabela.to_csv(ARQ_SAIDA, index=False)

# Onde os métodos divergem, no corte de maior sobreposição
melhor = int(tabela.sort_values("sobreposicao_pct", ascending=False).iloc[0]["corte_dias_sem_movimento"])
regra = ativos["dias_sem_movimento"] > melhor
partes = {
    "Os dois marcam": ativos[regra & alta],
    "Só a regra marca": ativos[regra & ~alta],
    "Só o K-Means marca": ativos[~regra & alta],
}
print(f"\nCorte de maior concordância: {melhor} dias. Mediana de cada parte:")
resumo = pd.DataFrame({
    nome: p[["dias_sem_movimento", "dias_tramitacao", "qtd_movimentos"]].median()
    for nome, p in partes.items()
}).T.round(0)
resumo.insert(0, "processos", [len(p) for p in partes.values()])
print(resumo.to_string())
print(f"\nTabela salva em {ARQ_SAIDA}")
