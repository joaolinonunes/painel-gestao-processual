import json
from collections import Counter

cont = Counter()
with open("data/raw/processos_raw.jsonl", encoding="utf-8") as f:
    for linha in f:
        for m in json.loads(linha).get("movimentos") or []:
            cont[(m.get("codigo"), m.get("nome"))] += 1

print("40 movimentos mais comuns:")
for (codigo, nome), qtd in cont.most_common(40):
    print(codigo, nome, qtd)

print()
print("Movimentos que parecem encerramento:")
palavras = ("arquiv", "baixa", "transit", "extin", "encerr", "definitiv")
for (codigo, nome), qtd in sorted(cont.items(), key=lambda x: -x[1]):
    if any(p in (nome or "").lower() for p in palavras):
        print(codigo, nome, qtd)
