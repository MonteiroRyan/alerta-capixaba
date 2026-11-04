import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dados.registry import ConjuntoDados  # noqa: E402
from dados.repositorio import abrir_conexao  # noqa: E402

CELULAR = ConjuntoDados("roubo-celular", "Roubo de celular", "A", "x", "roubo-celular.csv", {})
HOMICIDIO = ConjuntoDados("homicidios-e-feminicidios", "Homicídios e feminicídios", "B", "y", "h.csv", {})
CONJUNTOS = {c.id: c for c in (CELULAR, HOMICIDIO)}


def linha(ocorrencia, bairro, faixa, sexo=None, idade=None, municipio="VITORIA"):
    return {"ocorrencia": ocorrencia, "data_fato": pd.Timestamp("2024-03-10").date(), "faixa_horaria": faixa,
            "municipio": municipio, "bairro": bairro, "sexo": sexo, "cor_raca": None, "idade": idade}


@pytest.fixture
def con(tmp_path):
    celular = [linha("1", "CENTRO", "noite"), linha("1", "CENTRO", "noite"),  # 2 objetos, 1 ocorrência
               linha("2", "CENTRO", "manha"), linha("3", "JARDIM CAMBURI", "noite")]
    homicidio = [linha(str(i), "CENTRO", "noite", sexo="MASCULINO", idade=20) for i in range(6)]
    homicidio += [linha("9", "CENTRO", "tarde", sexo="FEMININO", idade=30)]
    caminhos = {}
    for cid, linhas in (("roubo-celular", celular), ("homicidios-e-feminicidios", homicidio)):
        caminhos[cid] = tmp_path / f"{cid}.parquet"
        df = pd.DataFrame(linhas)
        df["idade"] = df["idade"].astype("Int64")
        df.to_parquet(caminhos[cid])
    return abrir_conexao(caminhos)
