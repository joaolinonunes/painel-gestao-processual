import json

import pandas as pd

from config import ARQ_RAW, ARQ_PROCESSADO

CODIGOS_ARQUIVAMENTO = {22, 246, 12430}


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
