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
                "lte": f"{ano}{fim}235959"}}},
        ]}},
    }


def buscar(consulta, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.post(URL_API, headers=HEADERS, json=consulta, timeout=300)
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
                time.sleep(10)  # não sobrecarregar a API
    print(f"Coleta concluída: {total} processos em {ARQ_RAW}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "teste":
        testar()
    else:
        coletar()
