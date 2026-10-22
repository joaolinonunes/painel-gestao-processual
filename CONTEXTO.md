# Contexto de desenvolvimento – Painel de Apoio à Gestão Processual (PI IV)

Oct 20, 2026 · @João Batista

## 1. Visão geral do projeto

O projeto é um painel web que mostra onde estão os atrasos em processos judiciais, usando dados públicos do DataJud (CNJ) e o algoritmo K-Means para separar os processos em grupos como rápidos, médios e lentos. Ele faz parte do Projeto Integrador IV (UNIVESP) e precisa ficar coerente com o que está descrito no relatório.

**Objetivo:** ajudar gestores e servidores a identificar, de forma visual, os processos com maior tempo de tramitação e as classes processuais que mais demoram.

**Escopo mínimo (o que precisa existir na entrega):**

- Script que coleta dados da API Pública do DataJud;
- Script que trata os dados e calcula tempo de tramitação e quantidade de movimentações;
- Aplicação do K-Means com avaliação pelo coeficiente de silhueta;
- Painel em Streamlit com indicadores, gráficos, filtros e lista dos processos mais lentos;
- Código no GitHub e painel publicado;
- Validação com profissionais da área jurídica.

**Restrições que vêm do relatório:**

- Custo zero: só ferramentas gratuitas e de código aberto;
- Apenas dados públicos, sem dados pessoais das partes (LGPD);
- O painel é apoio à gestão: ele não sugere decisões judiciais;
- Recorte pequeno: TJSP, uma ou duas classes processuais (a definir pelo grupo).

## 2. Arquitetura, fluxo e estrutura de pastas

A solução é um fluxo em linha reta de quatro scripts Python, em que cada etapa gera um arquivo usado pela próxima. Não há banco de dados: tudo fica em arquivos CSV ou Parquet dentro do repositório.

1. **Coleta** (`src/coleta.py`): chama a API do DataJud e salva o retorno bruto em `data/raw/processos_raw.jsonl`.
2. **Tratamento** (`src/tratamento.py`): lê o bruto, limpa, calcula os indicadores e salva `data/processed/processos.csv`.
3. **Modelo** (`src/modelo.py`): aplica o K-Means, testa valores de K e salva `data/processed/processos_agrupados.csv` e `data/processed/metricas_modelo.json`.
4. **Painel** (`app.py`): o Streamlit lê os arquivos processados e mostra indicadores, gráficos e filtros.

Estrutura sugerida do repositório:

```
painel-gestao-processual/
├── app.py                  # painel Streamlit
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── secrets.toml        # chave da API (NÃO vai para o GitHub)
├── data/
│   ├── raw/                # retorno bruto da API (fora do Git se for grande)
│   └── processed/          # arquivos usados pelo painel
├── src/
│   ├── config.py           # tribunal, classes, caminhos
│   ├── coleta.py
│   ├── tratamento.py
│   └── modelo.py
├── notebooks/
│   └── exploracao.ipynb    # testes e gráficos para o relatório
└── docs/
    └── validacao.md        # registro das avaliações com profissionais
```

## 3. Ambiente e ferramentas

Tudo roda em Python 3.11 ou superior, com um ambiente virtual e seis bibliotecas gratuitas.

| Ferramenta | Para que serve | Custo |
| --- | --- | --- |
| Python 3.11+ | Linguagem do projeto inteiro | Gratuito |
| requests | Chamadas à API do DataJud | Gratuito |
| pandas | Tratamento dos dados | Gratuito |
| scikit-learn | K-Means, padronização e silhueta | Gratuito |
| streamlit | Painel web | Gratuito |
| plotly | Gráficos interativos no painel | Gratuito |
| pyarrow | Salvar em Parquet (opcional, arquivos menores) | Gratuito |
| Git + GitHub | Versionamento e colaboração | Gratuito |
| Streamlit Community Cloud | Publicação do painel | Plano gratuito |
| VS Code | Editor | Gratuito |

Preparação do ambiente:

```bash
git clone https://github.com/<usuario>/painel-gestao-processual.git
cd painel-gestao-processual
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

Conteúdo do `requirements.txt`:

```
requests
pandas>=2.2
scikit-learn>=1.5
streamlit>=1.50
plotly>=5.20
pyarrow
```

Conteúdo do `.gitignore`:

```
.venv/
__pycache__/
.streamlit/secrets.toml
data/raw/
```

## 4. Etapa 1 – Coleta de dados na API do DataJud

A coleta é um POST por página na API Pública do DataJud, com a chave pública no cabeçalho e uma consulta no formato do Elasticsearch, salvando cada processo como uma linha de JSON. Os códigos e campos abaixo vêm de memória: confiram tudo na [wiki oficial do DataJud](https://datajud-wiki.cnj.jus.br/api-publica/) antes de rodar.

**Dados da API (conferir na wiki):**

- Endpoint do TJSP: `https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search` (cada tribunal tem o seu sufixo);
- Cabeçalho: `Authorization: APIKey <chave pública>`; a chave é divulgada na wiki e pode ser trocada pelo CNJ;
- Máximo de 10.000 registros por página; para mais, usar paginação com `search_after` ordenando por `@timestamp`;
- Os processos vêm em `hits.hits[]._source`.

**Campos principais de cada processo:**

| Campo | O que contém | Uso no projeto |
| --- | --- | --- |
| `numeroProcesso` | Número do processo | Identificação |
| `classe.codigo` / `classe.nome` | Classe processual (TPU) | Filtro e agrupamento |
| `assuntos[]` | Lista de assuntos | Filtro opcional |
| `orgaoJulgador.nome` / `codigoMunicipioIBGE` | Vara e município | Recorte por comarca |
| `grau` | G1, G2, JE etc. | Filtro e remoção de duplicados |
| `dataAjuizamento` | Data de início | Cálculo do tempo |
| `movimentos[]` (`codigo`, `nome`, `dataHora`) | Histórico de andamento | Quantidade, última movimentação, arquivamento |
| `dataHoraUltimaAtualizacao` | Última atualização no DataJud | Controle |

**Sugestões de recorte (conferir códigos na Tabela Processual Unificada do CNJ):** classe 436 (Procedimento do Juizado Especial Cível) e/ou classe 7 (Procedimento Comum Cível), no município de São José do Rio Preto (código IBGE 3549805). Comecem com um limite de 5.000 processos.

`src/config.py`:

```python
from pathlib import Path

TRIBUNAL = "tjsp"
URL_API = f"https://api-publica.datajud.cnj.jus.br/api_publica_{TRIBUNAL}/_search"

CLASSES = [436]                  # conferir na TPU
CODIGO_MUNICIPIO_IBGE = 3549805  # São José do Rio Preto (conferir)
LIMITE_PROCESSOS = 5000
TAMANHO_PAGINA = 1000

BASE = Path(__file__).resolve().parent.parent
ARQ_RAW = BASE / "data" / "raw" / "processos_raw.jsonl"
ARQ_PROCESSADO = BASE / "data" / "processed" / "processos.csv"
ARQ_AGRUPADO = BASE / "data" / "processed" / "processos_agrupados.csv"
ARQ_METRICAS = BASE / "data" / "processed" / "metricas_modelo.json"
```

`src/coleta.py`:

```python
import json
import os
import time

import requests

from config import (URL_API, CLASSES, CODIGO_MUNICIPIO_IBGE,
                    LIMITE_PROCESSOS, TAMANHO_PAGINA, ARQ_RAW)

API_KEY = os.environ.get("DATAJUD_API_KEY")  # chave pública da wiki
if not API_KEY:
    raise SystemExit("Defina a variável de ambiente DATAJUD_API_KEY")

HEADERS = {"Authorization": f"APIKey {API_KEY}",
           "Content-Type": "application/json"}


def montar_consulta(search_after=None):
    consulta = {
        "size": TAMANHO_PAGINA,
        "query": {"bool": {"must": [
            {"terms": {"classe.codigo": CLASSES}},
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": CODIGO_MUNICIPIO_IBGE}},
        ]}},
        "sort": [{"@timestamp": {"order": "asc"}}],
    }
    if search_after:
        consulta["search_after"] = search_after
    return consulta


def buscar_pagina(consulta, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.post(URL_API, headers=HEADERS, json=consulta, timeout=60)
            r.raise_for_status()
            return r.json()["hits"]["hits"]
        except requests.RequestException as erro:
            print(f"Erro na tentativa {i + 1}: {erro}")
            time.sleep(5 * (i + 1))
    raise RuntimeError("Falha ao consultar a API")


def coletar():
    ARQ_RAW.parent.mkdir(parents=True, exist_ok=True)
    total, search_after = 0, None
    with open(ARQ_RAW, "w", encoding="utf-8") as arq:
        while total < LIMITE_PROCESSOS:
            hits = buscar_pagina(montar_consulta(search_after))
            if not hits:
                break
            for h in hits:
                arq.write(json.dumps(h["_source"], ensure_ascii=False) + "\n")
            total += len(hits)
            search_after = hits[-1]["sort"]
            print(f"{total} processos coletados")
            time.sleep(1)  # não sobrecarregar a API
    print(f"Coleta concluída: {total} processos em {ARQ_RAW}")


if __name__ == "__main__":
    coletar()
```

Para rodar: definir a variável `DATAJUD_API_KEY` com a chave da wiki e executar `python src/coleta.py`. Antes do script completo, vale testar uma consulta com `size: 5` e abrir o JSON para conferir os campos reais.

### 4.1 Atualização depois do teste real da API (usar esta versão)

O teste com a API real mudou a estratégia de coleta; **esta subseção substitui o `coleta.py` e o trecho de recorte do `config.py` acima**.

**O que o teste mostrou:**

- A primeira consulta (ordenada por `@timestamp` crescente) devolvia os primeiros registros carregados na base: processos antigos e **sem o campo `movimentos`**. Sem ele não existem `qtd_movimentos`, `dias_sem_movimento` nem `arquivado`;
- Com o filtro `exists: movimentos`, o TJSP devolve processos com histórico (83 movimentos no exemplo do JEC de São José do Rio Preto);
- Consultas com `sort` e contagem total chegaram a dar erro 504 (timeout) ou levar 45 s para 5 processos; sem eles levaram de 14 a 18 s para 2 processos;
- Sem `sort` não há paginação com `search_after`. A coleta passou a ser **fatiada por trimestre de ajuizamento**, com até 200 processos por trimestre (8 anos x 4 trimestres = no máximo 6.400 processos).

**Limitações que precisam constar no relatório:**

- A amostra só contém processos que têm histórico de movimentos; processos sem esse campo ficam de fora;
- A API não ordena: a amostra de cada trimestre não é aleatória;
- Como o número por trimestre é fixo, o gráfico "Processos por ano" reflete o tamanho da amostra e **não o volume real** da comarca; no painel, renomear para "Processos na amostra, por ano" ou remover;
- Consultas de teste do recorte antigo (sem `exists`) trouxeram processos da Fazenda Pública com assuntos de litigância em massa; com o filtro de movimentos, o recorte passou a ser o Juizado Especial Cível.

`src/config.py` (substitui o anterior):

```python
from pathlib import Path

TRIBUNAL = "tjsp"
URL_API = f"https://api-publica.datajud.cnj.jus.br/api_publica_{TRIBUNAL}/_search"

CLASSES = [436]                  # Procedimento do Juizado Especial Cível
CODIGO_MUNICIPIO_IBGE = 3549805  # São José do Rio Preto

# A coleta é fatiada por trimestre de ajuizamento (sem paginação)
ANO_INICIO = 2019
ANO_FIM = 2026
PROCESSOS_POR_TRIMESTRE = 200

BASE = Path(__file__).resolve().parent.parent
ARQ_RAW = BASE / "data" / "raw" / "processos_raw.jsonl"
ARQ_PROCESSADO = BASE / "data" / "processed" / "processos.csv"
ARQ_AGRUPADO = BASE / "data" / "processed" / "processos_agrupados.csv"
ARQ_METRICAS = BASE / "data" / "processed" / "metricas_modelo.json"
```

`src/coleta.py` (substitui o anterior):

```python
import json
import os
import sys
import time

import requests

from config import (URL_API, CLASSES, CODIGO_MUNICIPIO_IBGE, ANO_INICIO, ANO_FIM,
                    PROCESSOS_POR_TRIMESTRE, ARQ_RAW)

API_KEY = os.environ.get("DATAJUD_API_KEY")  # só a chave, sem "APIKey"
if not API_KEY:
    raise SystemExit("Defina a variável de ambiente DATAJUD_API_KEY")

HEADERS = {"Authorization": f"APIKey {API_KEY}", "Content-Type": "application/json"}
TRIMESTRES = [("0101", "0331"), ("0401", "0630"), ("0701", "0930"), ("1001", "1231")]


def montar_consulta(ano, tri, tamanho):
    ini, fim = TRIMESTRES[tri]
    return {
        "size": tamanho,
        "track_total_hits": False,  # evita a contagem total, que deixa a API lenta
        "query": {"bool": {"filter": [
            {"terms": {"classe.codigo": CLASSES}},
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": CODIGO_MUNICIPIO_IBGE}},
            {"exists": {"field": "movimentos"}},
            {"range": {"dataAjuizamento": {
                "gte": f"{ano}{ini}000000",
                "lte": f"{ano}{fim}235959",
                "format": "yyyyMMddHHmmss"}}},
        ]}},
    }


def buscar(consulta, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.post(URL_API, headers=HEADERS, json=consulta, timeout=180)
            if r.status_code == 400:  # consulta inválida: não adianta repetir
                raise SystemExit(f"Consulta recusada (400): {r.text[:600]}")
            r.raise_for_status()
            return r.json()["hits"]["hits"]
        except requests.RequestException as erro:
            print(f"  erro na tentativa {i + 1}: {erro}")
            time.sleep(10 * (i + 1))
    return None


def testar():
    """Uma única consulta pequena para conferir filtros e tempo."""
    inicio = time.time()
    hits = buscar(montar_consulta(2024, 0, 5))
    print(f"Tempo: {time.time() - inicio:.1f} s")
    if hits is None:
        raise SystemExit("A API não respondeu")
    print(f"Processos retornados: {len(hits)}")
    for h in hits:
        s = h["_source"]
        print(s.get("numeroProcesso"), s.get("dataAjuizamento"), len(s.get("movimentos") or []), "movimentos")


def coletar():
    ARQ_RAW.parent.mkdir(parents=True, exist_ok=True)
    vistos, total = set(), 0
    with open(ARQ_RAW, "w", encoding="utf-8") as arq:
        for ano in range(ANO_INICIO, ANO_FIM + 1):
            for tri in range(4):
                hits = buscar(montar_consulta(ano, tri, PROCESSOS_POR_TRIMESTRE))
                if hits is None:
                    print(f"{ano} T{tri + 1}: falhou, seguindo para o próximo")
                    continue
                novos = 0
                for h in hits:
                    s = h["_source"]
                    chave = (s.get("numeroProcesso"), s.get("grau"))
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    arq.write(json.dumps(s, ensure_ascii=False) + "\n")
                    novos += 1
                total += novos
                print(f"{ano} T{tri + 1}: {novos} processos (acumulado: {total})")
                time.sleep(2)  # não sobrecarregar a API
    print(f"Coleta concluída: {total} processos em {ARQ_RAW}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "teste":
        testar()
    else:
        coletar()
```

**Como rodar:** primeiro `python src/coleta.py teste` (uma consulta com 5 processos; confere os filtros e o tempo). Se vier dado, rodar `python src/coleta.py`. A coleta completa pode levar de 15 a 30 minutos; o script mostra o andamento a cada trimestre. Erro 400 significa que a API recusou algum filtro (a mensagem aparece no terminal).

**Conferir os códigos de arquivamento:** o `tratamento.py` usa os códigos 246 e 22 (de memória). Depois da coleta, listar os movimentos mais comuns e procurar os que indicam arquivamento ou baixa:

```python
import json
from collections import Counter

cont = Counter()
with open("data/raw/processos_raw.jsonl", encoding="utf-8") as f:
    for linha in f:
        for m in json.loads(linha).get("movimentos") or []:
            cont[(m.get("codigo"), m.get("nome"))] += 1

for (codigo, nome), qtd in cont.most_common(40):
    print(codigo, nome, qtd)
```

## 5. Etapa 2 – Tratamento dos dados

O tratamento transforma cada processo em uma linha com cinco indicadores numéricos e remove registros inválidos ou duplicados. Esses indicadores alimentam tanto o painel quanto o K-Means.

**Indicadores calculados por processo:**

| Coluna | Como calcular |
| --- | --- |
| `dias_tramitacao` | Data final menos `dataAjuizamento`; data final = data do arquivamento se houver, senão a data da coleta |
| `qtd_movimentos` | Tamanho da lista `movimentos` |
| `dias_sem_movimento` | Data da coleta menos a data da última movimentação |
| `media_dias_entre_mov` | `dias_tramitacao` dividido por `qtd_movimentos` |
| `arquivado` | Verdadeiro se houver movimento de arquivamento ou baixa definitiva |

**Regras de limpeza:**

- Remover processos sem `dataAjuizamento` ou com data futura ou anterior a 1990;
- Remover processos com `dias_tramitacao` negativo;
- O mesmo número pode aparecer em mais de um grau: manter um registro por processo, de preferência o de 1º grau;
- As datas podem vir em dois formatos (`20190312000000` ou ISO, como `2019-03-12T00:00:00.000Z`): o código trata os dois.

Os códigos de arquivamento abaixo (246 e 22) vêm de memória da Tabela Processual Unificada: confiram na TPU e olhando os movimentos reais coletados.

`src/tratamento.py`:

```python
import json

import pandas as pd

from config import ARQ_RAW, ARQ_PROCESSADO

CODIGOS_ARQUIVAMENTO = {246, 22}  # conferir na TPU


def converter_data(valor):
    if not valor:
        return pd.NaT
    valor = str(valor)
    if valor.isdigit() and len(valor) >= 8:
        return pd.to_datetime(valor[:14], format="%Y%m%d%H%M%S", errors="coerce")
    data = pd.to_datetime(valor, errors="coerce", utc=True)
    return data.tz_convert(None) if pd.notna(data) else pd.NaT


def extrair(processo, data_coleta):
    movimentos = processo.get("movimentos") or []
    datas_mov = [converter_data(m.get("dataHora")) for m in movimentos]
    datas_mov = [d for d in datas_mov if pd.notna(d)]

    datas_arquiv = [converter_data(m.get("dataHora")) for m in movimentos
                    if m.get("codigo") in CODIGOS_ARQUIVAMENTO]
    datas_arquiv = [d for d in datas_arquiv if pd.notna(d)]

    ajuizamento = converter_data(processo.get("dataAjuizamento"))
    data_final = max(datas_arquiv) if datas_arquiv else data_coleta
    ultimo_mov = max(datas_mov) if datas_mov else pd.NaT

    return {
        "numero_processo": processo.get("numeroProcesso"),
        "grau": processo.get("grau"),
        "classe": (processo.get("classe") or {}).get("nome"),
        "orgao_julgador": (processo.get("orgaoJulgador") or {}).get("nome"),
        "assunto": ((processo.get("assuntos") or [{}])[0] or {}).get("nome"),
        "data_ajuizamento": ajuizamento,
        "data_ultimo_movimento": ultimo_mov,
        "qtd_movimentos": len(movimentos),
        "arquivado": bool(datas_arquiv),
        "dias_tramitacao": (data_final - ajuizamento).days if pd.notna(ajuizamento) else None,
        "dias_sem_movimento": (data_coleta - ultimo_mov).days if pd.notna(ultimo_mov) else None,
    }


def tratar():
    data_coleta = pd.Timestamp.now().normalize()
    with open(ARQ_RAW, encoding="utf-8") as arq:
        linhas = [extrair(json.loads(l), data_coleta) for l in arq if l.strip()]

    df = pd.DataFrame(linhas)
    antes = len(df)

    df = df.dropna(subset=["data_ajuizamento", "dias_tramitacao"])
    df = df[(df["data_ajuizamento"] >= "1990-01-01") &
            (df["data_ajuizamento"] <= data_coleta) &
            (df["dias_tramitacao"] >= 0)]

    df["prioridade_grau"] = (df["grau"] != "G1").astype(int)
    df = (df.sort_values(["numero_processo", "prioridade_grau"])
            .drop_duplicates("numero_processo")
            .drop(columns="prioridade_grau"))

    # Processo arquivado não está "parado": zera o tempo sem movimento
    df.loc[df["arquivado"], "dias_sem_movimento"] = 0

    df["media_dias_entre_mov"] = df["dias_tramitacao"] / df["qtd_movimentos"].clip(lower=1)
    df["ano_ajuizamento"] = df["data_ajuizamento"].dt.year

    ARQ_PROCESSADO.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARQ_PROCESSADO, index=False)
    print(f"{antes} registros lidos, {len(df)} mantidos após a limpeza")


if __name__ == "__main__":
    tratar()
```

Para o relatório, anotem quantos registros foram lidos e quantos ficaram depois da limpeza: o script já imprime esses dois números.

## 6. Etapa 3 – Agrupamento com K-Means

O K-Means usa três variáveis (dias de tramitação, quantidade de movimentos e dias sem movimento), testa K de 2 a 6 e fixa K = 3 para gerar os grupos Rápido, Médio e Lento. O script abaixo foi testado com dados simulados e roda sem erros.

**Decisões do modelo:**

- **Transformação logarítmica (`log1p`):** tempos de tramitação têm muitos valores altos e isolados; o log reduz esse efeito;
- **Padronização (`StandardScaler`):** deixa as três variáveis na mesma escala, o que o K-Means exige;
- **Escolha de K:** o script imprime a inércia (método do cotovelo) e a silhueta para K de 2 a 6. K = 3 é o padrão por ser fácil de interpretar; se K = 4 tiver silhueta bem melhor, o grupo pode trocar `K_ESCOLHIDO`;
- **Nomes dos grupos:** os grupos saem do algoritmo numerados ao acaso; o script ordena pelo tempo médio de tramitação e dá os nomes.

`src/modelo.py`:

```python
import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import ARQ_PROCESSADO, ARQ_AGRUPADO, ARQ_METRICAS

VARIAVEIS = ["dias_tramitacao", "qtd_movimentos", "dias_sem_movimento"]
K_ESCOLHIDO = 3
NOMES_GRUPOS = {3: ["Rápido", "Médio", "Lento"],
                4: ["Rápido", "Médio", "Lento", "Muito lento"]}


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
    df = pd.read_csv(ARQ_PROCESSADO, parse_dates=["data_ajuizamento", "data_ultimo_movimento"])
    X = preparar(df)

    testes = testar_k(X)

    modelo = KMeans(n_clusters=K_ESCOLHIDO, n_init=10, random_state=42).fit(X)
    df["cluster"] = modelo.labels_

    # Ordena os grupos pelo tempo médio de tramitação e dá nomes
    ordem = df.groupby("cluster")["dias_tramitacao"].mean().sort_values().index
    nomes = NOMES_GRUPOS.get(K_ESCOLHIDO, [f"Grupo {i + 1}" for i in range(K_ESCOLHIDO)])
    df["grupo"] = df["cluster"].map(dict(zip(ordem, nomes)))

    resumo = (df.groupby("grupo")[VARIAVEIS]
                .agg(["mean", "median"]).round(1))
    print(resumo)

    metricas = {
        "k_escolhido": K_ESCOLHIDO,
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
```

**Como ler a silhueta:** vai de -1 a 1. Acima de 0,5 indica grupos bem separados; entre 0,25 e 0,5, separação razoável; abaixo de 0,25, grupos pouco definidos. A tabela de K testados e o resumo de cada grupo que o script imprime servem direto para a seção de resultados do relatório.

## 7. Etapa 4 – Painel em Streamlit

O painel lê os arquivos já processados e mostra quatro indicadores, quatro gráficos, a lista dos 50 processos parados há mais tempo e as métricas do modelo. O código abaixo foi testado com dados simulados no Streamlit 1.66 e roda sem erros.

**O que o painel mostra:**

- **Filtros na barra lateral:** classe, órgão julgador, ano de ajuizamento, grupo do K-Means e situação (em andamento ou arquivado);
- **Indicadores:** total de processos, tempo médio de tramitação, quantos estão em andamento e quantos estão no grupo Lento;
- **Gráficos:** tempo médio por classe, processos por ano, processos por grupo e dispersão de movimentações por tempo de tramitação;
- **Tabela:** processos em andamento há mais tempo sem movimentação;
- **Sobre o modelo:** K escolhido, silhueta, resultado dos K testados e mediana das variáveis em cada grupo.

`app.py` (na raiz do repositório):

```python
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).resolve().parent
ARQ_AGRUPADO = BASE / "data" / "processed" / "processos_agrupados.csv"
ARQ_METRICAS = BASE / "data" / "processed" / "metricas_modelo.json"
ORDEM_GRUPOS = ["Rápido", "Médio", "Lento", "Muito lento"]
CORES = {"Rápido": "#2e7d32", "Médio": "#f9a825", "Lento": "#c62828", "Muito lento": "#6a1b9a"}

st.set_page_config(page_title="Painel de Gestão Processual", page_icon="⚖️", layout="wide")


@st.cache_data
def carregar():
    df = pd.read_csv(ARQ_AGRUPADO, parse_dates=["data_ajuizamento", "data_ultimo_movimento"])
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
c4.metric("No grupo Lento", f"{(f['grupo'].isin(['Lento', 'Muito lento'])).sum():,}".replace(",", "."))

# ---------- Gráficos ----------
col_a, col_b = st.columns(2)

tempo_classe = (f.groupby("classe", as_index=False)["dias_tramitacao"].mean()
                  .sort_values("dias_tramitacao"))
col_a.plotly_chart(px.bar(tempo_classe, x="dias_tramitacao", y="classe", orientation="h",
                          title="Tempo médio de tramitação por classe",
                          labels={"dias_tramitacao": "Dias", "classe": ""}),
                   width="stretch")

por_ano = f.groupby("ano_ajuizamento").size().reset_index(name="processos")
col_b.plotly_chart(px.line(por_ano, x="ano_ajuizamento", y="processos", markers=True,
                           title="Processos por ano de ajuizamento",
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
```

Para rodar localmente: `streamlit run app.py`. O painel abre no navegador em `http://localhost:8501`.

**Acessibilidade:** as cores dos grupos vêm sempre acompanhadas do nome do grupo (legenda e tabela), então a informação não depende só da cor.

## 8. Etapa 5 – Publicação

O painel é publicado de graça no Streamlit Community Cloud, direto do repositório do GitHub; os dados processados vão junto no repositório, então o painel publicado não chama a API.

1. Criar um repositório público no GitHub com a estrutura da seção 2 e fazer o primeiro commit.
2. Rodar coleta, tratamento e modelo localmente e subir apenas `data/processed/` (o `.gitignore` já deixa `data/raw/` de fora).
3. Conferir o tamanho: o GitHub recusa arquivos acima de 100 MB. Com 5.000 processos o CSV fica bem abaixo disso; se crescer, salvar em Parquet (`df.to_parquet(...)`).
4. Entrar em share.streamlit.io com a conta do GitHub, clicar em criar app, escolher o repositório, a branch `main` e o arquivo `app.py`.
5. Aguardar a instalação das bibliotecas do `requirements.txt` e testar o link gerado.
6. Para atualizar os dados: rodar os scripts de novo, fazer commit dos arquivos processados e o painel se atualiza sozinho.

**Chave da API:** mesmo sendo pública, não deve ir para o GitHub. Localmente, fica na variável de ambiente `DATAJUD_API_KEY`. Como a coleta roda só na máquina de quem coleta, o painel publicado não precisa da chave.

**Boas práticas no GitHub:** cada integrante trabalha em uma branch própria e abre pull request para a `main`; o `README.md` explica o projeto e como rodar cada script.

## 9. Etapa 6 – Validação com profissionais

A validação é uma conversa de 15 a 20 minutos com cada profissional (servidor, advogado ou estagiário de fórum), em que ele usa o painel e responde seis perguntas. Isso cumpre a etapa de testes do Design Thinking e gera material para a seção de resultados.

**Roteiro da conversa:**

1. Explicar em dois minutos o objetivo do painel e de onde vêm os dados.
2. Pedir que a pessoa use os filtros livremente por alguns minutos, observando onde ela tem dificuldade.
3. Fazer as perguntas abaixo e anotar as respostas.
4. Agradecer e perguntar se pode ser citada no relatório (por cargo, sem nome).

**Perguntas (nota de 1 a 5 mais um comentário):**

| Nº | Pergunta |
| --- | --- |
| 1 | As informações do painel são fáceis de entender? |
| 2 | Os grupos Rápido, Médio e Lento fazem sentido com o que você vê no dia a dia? |
| 3 | A lista de processos parados seria útil para a gestão da sua unidade? |
| 4 | Que informação está faltando no painel? |
| 5 | Você usaria uma ferramenta assim no trabalho? Por quê? |
| 6 | O que você mudaria primeiro? |

**Registro:** anotar em `docs/validacao.md` a data, o cargo do participante, as notas e os comentários. No relatório, apresentar a média das notas e os comentários mais relevantes, sem identificar as pessoas.

## 10. LGPD, ética e problemas comuns

O projeto só usa metadados públicos e não guarda dados das partes; os cuidados abaixo mantêm isso verdadeiro e coerente com o que o relatório afirma.

**Cuidados com LGPD e ética:**

- Conferir na primeira coleta se o retorno traz algum dado pessoal; se trouxer, não salvar esse campo;
- Não cruzar o número do processo com outras fontes para descobrir quem são as partes;
- Manter no painel o aviso de que ele é apoio à gestão e não substitui a análise humana;
- Na validação, não registrar nomes dos participantes, só o cargo.

**Problemas comuns e como resolver:**

| Problema | Causa provável | Solução |
| --- | --- | --- |
| Erro 401 ou 403 na API | Chave errada ou trocada pelo CNJ | Copiar de novo a chave atual da wiki do DataJud |
| Nenhum processo retornado | Código de classe ou município errado | Testar a consulta sem filtros com `size: 5` e ver os códigos reais |
| Coleta para na 10.000ª linha | Faltou a paginação | Usar `search_after`, como no script |
| Erro de timeout | API lenta ou consulta grande | Diminuir `TAMANHO_PAGINA` para 500 e manter a pausa entre páginas |
| Datas vazias depois do tratamento | Formato de data diferente | Imprimir alguns valores brutos e ajustar `converter_data` |
| Grupos sem sentido no K-Means | Valores extremos ou variáveis mal escolhidas | Conferir o `log1p`, remover outliers e testar outro K |
| Painel lento | Arquivo grande demais | Usar Parquet e manter o `@st.cache_data` |
| Erro ao publicar no Streamlit Cloud | Biblioteca faltando | Conferir o `requirements.txt` e o log de instalação |

## 11. Divisão de tarefas, cronograma e checklist

Com oito integrantes, o trabalho cabe em cerca de seis semanas, com a coleta e o tratamento como caminho crítico: o modelo e o painel dependem deles.

**Divisão sugerida:**

| Frente | Pessoas | Responsabilidade |
| --- | --- | --- |
| Coleta | 2 | Testar a API, definir o recorte, rodar `coleta.py` |
| Tratamento e modelo | 2 | `tratamento.py`, `modelo.py`, análise da silhueta |
| Painel e publicação | 2 | `app.py`, ajustes visuais, Streamlit Cloud |
| Validação | 1 | Contatar profissionais, aplicar o roteiro, registrar |
| Relatório e referências | 1 | Integrar textos, prints, resultados e ABNT |

**Cronograma (semanas a partir do início do desenvolvimento):**

| Semana | Entrega |
| --- | --- |
| 1 | Repositório criado, ambiente instalado, primeira consulta à API com `size: 5` |
| 2 | Coleta completa e recorte definido (classes e município) |
| 3 | Tratamento concluído e números de limpeza anotados |
| 4 | K-Means aplicado, K escolhido, primeira versão do painel |
| 5 | Painel publicado e validação com profissionais |
| 6 | Ajustes pós-validação e seção de resultados no relatório |

**Evidências para o relatório:**

- [ ] Print de uma resposta da API (com dados anonimizados se necessário)
- [ ] Quantidade de registros coletados e mantidos após a limpeza
- [ ] Tabela de K testados com inércia e silhueta
- [ ] Resumo dos grupos (mediana de cada variável)
- [ ] Prints das telas do painel
- [ ] Link do repositório no GitHub e do painel publicado
- [ ] Resultado da validação (média das notas e comentários)
- [ ] Preencher no relatório as classes escolhidas e o número de profissionais

## 12. Como usar este contexto com um assistente de IA

Para pedir ajuda a um assistente de código (como o Claude Code), exportem este documento em Markdown e salvem como `CONTEXTO.md` na raiz do repositório, ou colem o resumo abaixo no início da conversa.

```markdown
Projeto: painel de apoio à gestão processual (PI IV – UNIVESP).
Objetivo: identificar processos judiciais com maior tempo de tramitação.
Dados: API Pública do DataJud (CNJ), TJSP, recorte por classe e município.
Stack: Python 3.11+, requests, pandas, scikit-learn (K-Means), Streamlit, plotly.
Fluxo: src/coleta.py -> data/raw/processos_raw.jsonl
       src/tratamento.py -> data/processed/processos.csv
       src/modelo.py -> data/processed/processos_agrupados.csv + metricas_modelo.json
       app.py (Streamlit) lê os arquivos processados.
Variáveis do modelo: dias_tramitacao, qtd_movimentos, dias_sem_movimento
(log1p + StandardScaler, K-Means com K=3, avaliado por silhueta).
Restrições: custo zero, só dados públicos sem dados pessoais (LGPD),
painel é apoio à gestão e não sugere decisões judiciais.
Tarefa atual: <descreva aqui o que precisa>
```

Ao pedir ajuda com um erro, mandem junto a mensagem de erro completa e, se for na coleta ou no tratamento, um exemplo de um processo do arquivo bruto (uma linha do `.jsonl`).
