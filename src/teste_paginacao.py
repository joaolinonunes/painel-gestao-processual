import os
import sys
import time
import requests

try:
    from config import URL_API, CLASSES, CODIGO_MUNICIPIO_IBGE
except ImportError:
    from src.config import URL_API, CLASSES, CODIGO_MUNICIPIO_IBGE

TIMEOUT_SECS = 180
INTERVALO_ENTRE_CONSULTAS = 45
PAUSA_RETRY_429 = 60
MAX_TENTATIVAS_429 = 4

# Filtros base presentes em todas as consultas
BASE_FILTERS = [
    {"terms": {"classe.codigo": CLASSES}},
    {"match": {"orgaoJulgador.codigoMunicipioIBGE": CODIGO_MUNICIPIO_IBGE}},
    {"exists": {"field": "movimentos"}},
]

# Definição das consultas G a K
CONSULTAS = [
    {
        "letra": "G",
        "descricao": "size 10, from 0",
        "size": 10,
        "from": 0,
        "filtros": BASE_FILTERS,
    },
    {
        "letra": "H",
        "descricao": "size 5, from 5",
        "size": 5,
        "from": 5,
        "filtros": BASE_FILTERS,
    },
    {
        "letra": "I",
        "descricao": "size 5, from 4900",
        "size": 5,
        "from": 4900,
        "filtros": BASE_FILTERS,
    },
    {
        "letra": "J",
        "descricao": 'filtro base + range dataAjuizamento gte "20240101", lte "20240331" (format: yyyyMMdd), size 3',
        "size": 3,
        "from": 0,
        "filtros": BASE_FILTERS + [
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "20240101",
                        "lte": "20240331",
                        "format": "yyyyMMdd",
                    }
                }
            }
        ],
    },
    {
        "letra": "K",
        "descricao": 'filtro base + range dataAjuizamento gte "20240101000000", lte "20240331235959" (sem format), size 3',
        "size": 3,
        "from": 0,
        "filtros": BASE_FILTERS + [
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": "20240101000000",
                        "lte": "20240331235959",
                    }
                }
            }
        ],
    },
]


def executar_com_retry(headers, payload, max_tentativas=MAX_TENTATIVAS_429):
    """Executa a requisição com tratamento específico de retry para HTTP 429."""
    for tentativa in range(1, max_tentativas + 1):
        inicio = time.time()
        try:
            r = requests.post(URL_API, headers=headers, json=payload, timeout=TIMEOUT_SECS)
            duracao = time.time() - inicio

            if r.status_code == 429:
                print(f"  [Tentativa {tentativa}/{max_tentativas}] Erro HTTP 429 (Rate Limit).")
                if tentativa < max_tentativas:
                    print(f"  Aguardando {PAUSA_RETRY_429}s antes de tentar novamente...")
                    time.sleep(PAUSA_RETRY_429)
                    continue
                else:
                    return None, duracao, r.status_code, r.text[:400]

            if not r.ok:
                return None, duracao, r.status_code, r.text[:400]

            return r.json(), duracao, r.status_code, None

        except requests.RequestException as erro:
            duracao = time.time() - inicio
            status = getattr(getattr(erro, "response", None), "status_code", None)
            text = getattr(getattr(erro, "response", None), "text", str(erro))

            if status == 429:
                print(f"  [Tentativa {tentativa}/{max_tentativas}] Erro HTTP 429.")
                if tentativa < max_tentativas:
                    print(f"  Aguardando {PAUSA_RETRY_429}s antes de tentar novamente...")
                    time.sleep(PAUSA_RETRY_429)
                    continue
                else:
                    return None, duracao, status, text[:400]

            return None, duracao, status, text[:400]

    return None, 0, None, "Tentativas esgotadas"


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

    hits_g = []
    hits_h = []

    total_consultas = len(CONSULTAS)

    for i, item in enumerate(CONSULTAS):
        letra = item["letra"]
        print("=" * 70)
        print(f"Consulta {letra}: {item['descricao']}")

        payload = {
            "size": item["size"],
            "from": item["from"],
            "track_total_hits": False,
            "query": {
                "bool": {
                    "filter": item["filtros"],
                }
            },
        }

        dados, duracao, status, erro_msg = executar_com_retry(headers, payload)

        if dados is None:
            print(f"[{letra}] Falha na consulta (Status: {status}, Tempo: {duracao:.2f}s)")
            print(f"[{letra}] Detalhes: {erro_msg}")
        else:
            hits = dados.get("hits", {}).get("hits", [])
            print(f"[{letra}] Tempo gasto: {duracao:.2f}s | Processos retornados: {len(hits)}")

            if letra == "G":
                hits_g = hits
            elif letra == "H":
                hits_h = hits

            for idx, h in enumerate(hits, 1):
                s = h.get("_source", {})
                num = s.get("numeroProcesso", "N/A")
                data_aj = s.get("dataAjuizamento", "N/A")
                grau = s.get("grau", "N/A")
                movs = s.get("movimentos")
                qtd_movs = len(movs) if isinstance(movs, list) else 0
                print(f"  {idx}. numeroProcesso: {num} | dataAjuizamento: {data_aj} | grau: {grau} | movimentos: {qtd_movs}")

        # Comparação solicitada logo após a Consulta H
        if letra == "H":
            print("\n--- Comparação: Consulta H vs Itens 5 a 9 da Consulta G ---")
            numeros_g = [h.get("_source", {}).get("numeroProcesso", "N/A") for h in hits_g]
            numeros_h = [h.get("_source", {}).get("numeroProcesso", "N/A") for h in hits_h]

            sub_g = numeros_g[5:10]
            print(f"Consulta G [itens posição 5 a 9] ({len(sub_g)} itens): {sub_g}")
            print(f"Consulta H [todos os 5 itens]   ({len(numeros_h)} itens): {numeros_h}")

            if sub_g and sub_g == numeros_h:
                print("Resultado da comparação: IGUAL")
            else:
                print("Resultado da comparação: DIFERENTE")

        # Pausa de 45 segundos entre as consultas (exceto após a última)
        if i < total_consultas - 1:
            print(f"\nAguardando {INTERVALO_ENTRE_CONSULTAS} segundos antes da próxima consulta...")
            time.sleep(INTERVALO_ENTRE_CONSULTAS)

    print("=" * 70)
    print("Todas as consultas foram concluídas.")


if __name__ == "__main__":
    main()
