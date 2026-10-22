import json
import os
import sys
import time
from pathlib import Path
import requests

# Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
DIR_RAW = BASE_DIR / "data" / "raw"

# Parâmetros gerais
URL_TEMPLATE = "https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"
SIZE = 2
TIMEOUT_SECS = 180

# Definição das consultas D a H
CONSULTAS = [
    {
        "id": "D",
        "tribunal": "tjsp",
        "nome": "Consulta D (tjsp, apenas exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_D.json",
        "must": [
            {"exists": {"field": "movimentos"}},
        ],
    },
    {
        "id": "E",
        "tribunal": "tjsp",
        "nome": "Consulta E (tjsp, classe 436 + município 3549805 + exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_E.json",
        "must": [
            {"terms": {"classe.codigo": [436]}},
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": 3549805}},
            {"exists": {"field": "movimentos"}},
        ],
    },
    {
        "id": "F",
        "tribunal": "tjdft",
        "nome": "Consulta F (tjdft, apenas exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_F.json",
        "must": [
            {"exists": {"field": "movimentos"}},
        ],
    },
    {
        "id": "G",
        "tribunal": "tjmg",
        "nome": "Consulta G (tjmg, apenas exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_G.json",
        "must": [
            {"exists": {"field": "movimentos"}},
        ],
    },
    {
        "id": "H",
        "tribunal": "tjac",
        "nome": "Consulta H (tjac, apenas exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_H.json",
        "must": [
            {"exists": {"field": "movimentos"}},
        ],
    },
]


def executar_consulta(headers, item):
    url = URL_TEMPLATE.format(tribunal=item["tribunal"])
    print("=" * 70)
    print(f"Iniciando {item['nome']}...")
    print(f"Endpoint: {url}")

    # Consulta com size 2, track_total_hits false e SEM o campo sort
    payload = {
        "size": SIZE,
        "track_total_hits": False,
        "query": {
            "bool": {
                "must": item["must"],
            }
        },
    }

    inicio = time.time()
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECS,
        )
        duracao = time.time() - inicio
        response.raise_for_status()
        dados = response.json()
    except requests.RequestException as e:
        duracao = time.time() - inicio
        print(f"Erro na requisição ({item['id']}) após {duracao:.2f}s: {e}")
        return

    # Salva o retorno completo em disco
    item["arquivo"].parent.mkdir(parents=True, exist_ok=True)
    with open(item["arquivo"], "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print(f"Retorno salvo em: {item['arquivo']}")

    # Estatísticas no terminal
    hits = dados.get("hits", {}).get("hits", [])
    qtd_processos = len(hits)
    print(f"Tempo gasto: {duracao:.2f} segundos")
    print(f"Quantidade de processos retornados: {qtd_processos}")

    if not hits:
        print("Nenhum processo retornado em hits.hits.")
        return

    primeiro_source = hits[0].get("_source", {})
    num_proc = primeiro_source.get("numeroProcesso", "N/A")
    grau = primeiro_source.get("grau", "N/A")
    print(f"Primeiro processo: {num_proc} (grau: {grau})")

    if "movimentos" in primeiro_source:
        movs = primeiro_source.get("movimentos")
        if isinstance(movs, list):
            qtd_movs = len(movs)
            print(f"Campo 'movimentos': PRESENTE com {qtd_movs} itens")
            if qtd_movs > 0:
                ex = movs[0]
                cod = ex.get("codigo", "N/A")
                nome = ex.get("nome", "N/A")
                data_hora = ex.get("dataHora", "N/A")
                print("Exemplo de movimento (primeiro item):")
                print(f"  - codigo:   {cod}")
                print(f"  - nome:     {nome}")
                print(f"  - dataHora: {data_hora}")
            else:
                print("A lista 'movimentos' está vazia.")
        else:
            print(f"Campo 'movimentos': PRESENTE mas não é lista ({type(movs).__name__}).")
    else:
        print("Campo 'movimentos': NÃO EXISTE no primeiro processo.")


def main():
    api_key = os.environ.get("DATAJUD_API_KEY")
    if not api_key:
        print("Erro: A variável de ambiente DATAJUD_API_KEY não está definida.")
        print("Defina-a antes de executar o script, por exemplo:")
        print("  PowerShell: $env:DATAJUD_API_KEY = 'sua_chave'")
        print("  CMD:        set DATAJUD_API_KEY=sua_chave")
        print("  Linux/Mac:  export DATAJUD_API_KEY='sua_chave'")
        sys.exit(1)

    headers = {
        "Authorization": f"APIKey {api_key}",
        "Content-Type": "application/json",
    }

    for item in CONSULTAS:
        executar_consulta(headers, item)

    print("=" * 70)
    print("Processamento concluído.")


if __name__ == "__main__":
    main()
