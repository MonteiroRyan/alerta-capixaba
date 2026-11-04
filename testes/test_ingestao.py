import pandas as pd

from dados.ingestao import faixa_horaria, ler_csv, normalizar_texto, transformar
from dados.registry import ConjuntoDados


def test_faixa_horaria_rn03():
    assert faixa_horaria("00:00:00") == "madrugada"
    assert faixa_horaria("05:59") == "madrugada"
    assert faixa_horaria("06:00:00") == "manha"
    assert faixa_horaria("12:00:00") == "tarde"
    assert faixa_horaria("23:59:59") == "noite"
    assert faixa_horaria("Indeterminada") == "indeterminada"
    assert faixa_horaria(None) == "indeterminada"


def test_normalizacao_rn05():
    s = normalizar_texto(pd.Series(["  praia   da costa ", "1 - Masculino"]))
    assert list(s) == ["PRAIA DA COSTA", "MASCULINO"]


def test_le_latin1_ponto_e_virgula_e_deduplica(tmp_path):
    csv = tmp_path / "h.csv"
    conteudo = ("Nº OCORRENCIA;DATA;HORA;MUNICÍPIO;BAIRRO;IDADE;GENERO;COR\n"
                "1;01/01/2023;15:00:00;Vitória;São Pedro;20;1 - Masculino;S/I\n"
                "1;01/01/2023;15:00:00;Vitória;São Pedro;20;1 - Masculino;S/I\n")
    csv.write_bytes(conteudo.encode("latin-1"))
    campos = {"ocorrencia": "Nº OCORRENCIA", "data_fato": "DATA", "hora_fato": "HORA", "municipio": "MUNICÍPIO",
              "bairro": "BAIRRO", "idade": "IDADE", "sexo": "GENERO", "cor_raca": "COR"}
    df = transformar(ler_csv(csv), ConjuntoDados("h", "H", "B", "x", "h.csv", campos))
    assert len(df) == 1
    assert df.loc[0, "bairro"] == "SÃO PEDRO"
    assert df.loc[0, "sexo"] == "MASCULINO"
    assert pd.isna(df.loc[0, "cor_raca"])
    assert df.loc[0, "faixa_horaria"] == "tarde"
