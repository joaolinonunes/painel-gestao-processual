import json
import os
import sys
from pathlib import Path
import requests

# Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
DIR_RAW = BASE_DIR / "data" / "raw"

# Configurações gerais
URL_API = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"
MUNICIPIO_IBGE = 3549805
SIZE = 3
TIMEOUT_SECS = 180

# Definição das três consultas a serem testadas
CONSULTAS = [
    {
        "id": "A",
        "nome": "Consulta A (Classe 436 + Município 3549805 + exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_A.json",
        "must_clauses": [
            {"terms": {"classe.codigo": [436]}},
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": MUNICIPIO_IBGE}},
            {"exists": {"field": "movimentos"}},
        ],
    },
    {
        "id": "B",
        "nome": "Consulta B (Classe 7 + Município 3549805 + exists: movimentos)",
        "arquivo": DIR_RAW / "teste_mov_B.json",
        "must_clauses": [
            {"terms": {"classe.codigo": [7]}},
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": MUNICIPIO_IBGE}},
            {"exists": {"field": "movimentos"}},
        ],
    },
    {
        "id": "C",
        "nome": "Consulta C (Classe 436 + Município 3549805 + formato.codigo = 1)",
        "arquivo": DIR_RAW / "teste_mov_C.json",
        "must_clauses": [
            {"terms": {"classe.codigo": [436]}},
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": MUNICIPIO_IBGE}},
            {"match": {"formato.codigo": 1}},
        ],
    },
]


def executar_consulta(headers, item):
    print("=" * 70)
    print(f"Iniciando {item['nome']}...")
    payload = {
        "size": SIZE,
        "query": {
            "bool": {
                "must": item["must_clauses"],
            }
        },
        "sort": [{"@timestamp": {"order": "asc"}}],
    }

    try:
        response = requests.post(
            URL_API,
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro na requisição ({item['id']}): {e}")
        return

    dados = response.json()

    # Salva o retorno completo com indentação
    item["arquivo"].parent.mkdir(parents=True, exist_ok=True)
    with open(item["arquivo"], "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print(f"Retorno salvo em: {item['arquivo']}")

    # Estatísticas da resposta
    total_value = dados.get("hits", {}).get("total", {}).get("value", 0)
    total_relation = dados.get("hits", {}).get("total", {}).get("relation", "eq")
    print(f"hits.total.value: {total_value} (relação: {total_relation})")

    hits = dados.get("hits", {}).get("hits", [])
    if not hits:
        print("Nenhum processo retornado na página de resultados (hits.hits vazio).")
        return

    primeiro_source = hits[0].get("_source", {})
    numero_processo = primeiro_source.get("numeroProcesso", "N/A")
    formato = primeiro_source.get("formato", {})
    print(f"Primeiro processo retornado: {numero_processo} (formato: {formato})")

    if "movimentos" in primeiro_source:
        movs = primeiro_source.get("movimentos")
        if isinstance(movs, list):
            qtd = len(movs)
            print(f"Campo 'movimentos': PRESENTE com {qtd} itens")
            if qtd > 0:
                ex = movs[0]
                cod = ex.get("codigo", "N/A")
                nome = ex.get("nome", "N/A")
                data_hora = ex.get("dataHora", "N/A")
                print(f"Exemplo de movimento (primeiro item):")
                print(f"  - codigo:   {cod}")
                print(f"  - nome:     {nome}")
                print(f"  - dataHora: {data_hora}")
            else:
                print("A lista 'movimentos' está vazia.")
        else:
            print(f"Campo 'movimentos': PRESENTE mas não é lista ({type(movs).__name__}).")
    else:
        print("Campo 'movimentos': NÃO EXISTE no primeiro processo retornado.")


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
    print("Concluídas todas as consultas.")


if __name__ == "__main__":
    main()
