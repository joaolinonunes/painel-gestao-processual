from pathlib import Path

TRIBUNAL = "tjsp"
URL_API = f"https://api-publica.datajud.cnj.jus.br/api_publica_{TRIBUNAL}/_search"

CLASSES = [436]                  # Procedimento do Juizado Especial Cível
CODIGO_MUNICIPIO_IBGE = 3549805  # São José do Rio Preto

# A coleta é fatiada por trimestre de ajuizamento (sem paginação)
ANO_INICIO = 2019
ANO_FIM = 2026
PROCESSOS_POR_TRIMESTRE = 100

BASE = Path(__file__).resolve().parent.parent
ARQ_RAW = BASE / "data" / "raw" / "processos_raw.jsonl"
ARQ_PROCESSADO = BASE / "data" / "processed" / "processos.csv"
ARQ_AGRUPADO = BASE / "data" / "processed" / "processos_agrupados.csv"
ARQ_METRICAS = BASE / "data" / "processed" / "metricas_modelo.json"
