import os
import sys
import time
import requests

try:
    from config import URL_API, CLASSES, CODIGO_MUNICIPIO_IBGE
except ImportError:
    from src.config import URL_API, CLASSES, CODIGO_MUNICIPIO_IBGE

SIZE = 3
TIMEOUT_SECS = 180

# Filtros comuns a todas as consultas
BASE_FILTERS = [
    {"terms": {"classe.codigo": CLASSES}},
    {"match": {"orgaoJulgador.codigoMunicipioIBGE": CODIGO_MUNICIPIO_IBGE}},
]

EXISTS_MOVIMENTOS = {"exists": {"field": "movimentos"}}

# Definição das variações de filtro de data
CONSULTAS = [
    {
        "letra": "A",
        "descricao": 'range em dataAjuizamento: gte "2024-01-01", lte "2024-03-31", sem "format"',
        "filtros": BASE_FILTERS + [
            EXISTS_MOVIMENTOS,
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "2024-01-01",
                        "lte": "2024-03-31",
                    }
                }
            },
        ],
    },
    {
        "letra": "B",
        "descricao": 'range em dataAjuizamento: gte "20240101", lte "20240331", com "format": "yyyyMMdd"',
        "filtros": BASE_FILTERS + [
            EXISTS_MOVIMENTOS,
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "20240101",
                        "lte": "20240331",
                        "format": "yyyyMMdd",
                    }
                }
            },
        ],
    },
    {
        "letra": "C",
        "descricao": 'range em dataAjuizamento: gte "20240101000000", lte "20240331235959", sem "format"',
        "filtros": BASE_FILTERS + [
            EXISTS_MOVIMENTOS,
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "20240101000000",
                        "lte": "20240331235959",
                    }
                }
            },
        ],
    },
    {
        "letra": "D",
        "descricao": 'range em dataAjuizamento: gte "2024-01-01T00:00:00", lte "2024-03-31T23:59:59", com "format": "strict_date_optional_time"',
        "filtros": BASE_FILTERS + [
            EXISTS_MOVIMENTOS,
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "2024-01-01T00:00:00",
                        "lte": "2024-03-31T23:59:59",
                        "format": "strict_date_optional_time",
                    }
                }
            },
        ],
    },
    {
        "letra": "E",
        "descricao": 'sem nenhum filtro de data, mas com exists: movimentos',
        "filtros": BASE_FILTERS + [
            EXISTS_MOVIMENTOS,
        ],
    },
    {
        "letra": "F",
        "descricao": 'range igual ao A, mas sem o filtro exists de movimentos',
        "filtros": BASE_FILTERS + [
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "2024-01-01",
                        "lte": "2024-03-31",
                    }
                }
            },
        ],
    },
]


def executar_consulta(headers, item):
    letra = item["letra"]
    print("=" * 70)
    print(f"Consulta {letra}: {item['descricao']}")

    payload = {
        "size": SIZE,
        "track_total_hits": False,
        "query": {
            "bool": {
                "filter": item["filtros"]
            }
        },
    }

    inicio = time.time()
    try:
        r = requests.post(URL_API, headers=headers, json=payload, timeout=TIMEOUT_SECS)
        duracao = time.time() - inicio

        if not r.ok:
            print(f"[{letra}] Erro HTTP {r.status_code} ({duracao:.2f}s): {r.text[:400]}")
            return

        dados = r.json()
    except requests.RequestException as erro:
        duracao = time.time() - inicio
        if hasattr(erro, "response") and erro.response is not None:
            print(f"[{letra}] Erro HTTP {erro.response.status_code} ({duracao:.2f}s): {erro.response.text[:400]}")
        else:
            print(f"[{letra}] Erro na requisição ({duracao:.2f}s): {erro}")
        return

    hits = dados.get("hits", {}).get("hits", [])
    print(f"[{letra}] Tempo gasto: {duracao:.2f}s | Processos retornados: {len(hits)}")

    if not hits:
        print(f"[{letra}] Nenhum processo retornado.")
        return

    for idx, h in enumerate(hits, 1):
        s = h.get("_source", {})
        num = s.get("numeroProcesso", "N/A")
        data_aj = s.get("dataAjuizamento", "N/A")
        movs = s.get("movimentos")
        qtd_movs = len(movs) if isinstance(movs, list) else 0
        print(f"  {idx}. numeroProcesso: {num} | dataAjuizamento: {data_aj} | movimentos: {qtd_movs}")


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
    print("Testes concluídos.")


if __name__ == "__main__":
    main()
