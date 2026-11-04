import json
from datetime import datetime
from pathlib import Path


def registrar(arquivo: Path, pergunta: str, resposta: str, util: bool) -> None:
    linha = {"em": datetime.now().isoformat(timespec="seconds"), "pergunta": pergunta,
             "resposta": resposta, "util": util}
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
