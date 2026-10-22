import json
import os
import sys
from pathlib import Path
import requests

# Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "raw" / "teste_api.json"

# Configurações da consulta (conforme seção 4 do CONTEXTO.md)
URL_API = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"
CLASSE = 436
CODIGO_MUNICIPIO_IBGE = 3549805
SIZE = 5


def main():
    api_key = os.environ.get("DATAJUD_API_KEY")
    if not api_key:
        print("Erro: A variável de ambiente DATAJUD_API_KEY não está definida.")
        print("Defina a variável antes de executar o script, por exemplo:")
        print("  PowerShell: $env:DATAJUD_API_KEY = 'sua_chave'")
        print("  CMD:        set DATAJUD_API_KEY=sua_chave")
        print("  Linux/Mac:  export DATAJUD_API_KEY='sua_chave'")
        sys.exit(1)

    headers = {
        "Authorization": f"APIKey {api_key}",
        "Content-Type": "application/json",
    }

    consulta = {
        "size": SIZE,
        "query": {
            "bool": {
                "must": [
                    {"terms": {"classe.codigo": [CLASSE]}},
                    {"match": {"orgaoJulgador.codigoMunicipioIBGE": CODIGO_MUNICIPIO_IBGE}},
                ]
            }
        },
        "sort": [{"@timestamp": {"order": "asc"}}],
    }

    print(f"Consultando API Pública do DataJud ({URL_API})...")
    try:
        response = requests.post(URL_API, headers=headers, json=consulta, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro na requisição à API: {e}")
        sys.exit(1)

    dados = response.json()

    # Salva o retorno completo com indentação
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

    print(f"Retorno completo salvo com sucesso em: {OUTPUT_FILE}")

    hits = dados.get("hits", {}).get("hits", [])
    print(f"\nQuantidade de processos retornados: {len(hits)}")

    if hits:
        primeiro_processo = hits[0].get("_source", {})
        print("Chaves do primeiro processo (_source):")
        for chave in primeiro_processo.keys():
            print(f"  - {chave}")
    else:
        print("Nenhum registro encontrado em 'hits.hits'.")


if __name__ == "__main__":
    main()
