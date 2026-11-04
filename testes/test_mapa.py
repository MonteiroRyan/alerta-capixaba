import json

import pandas as pd
import pytest

from dados.ingestao import preparar_populacao
from dados.registry import carregar_mapa, carregar_registry
from dados.repositorio import abrir_conexao
from dominio.mapa import (classificar, criar_tabela_mapa, escala, historico, limites, orientar,
                          sem_ilhas_oceanicas, taxas)
from infra import config


@pytest.fixture
def con_mapa(tmp_path):
    populacao = tmp_path / "pop.csv"
    populacao.write_text("codigo_ibge,municipio,populacao\n3205309,Vitória,200000\n3204559,Santa Maria de Jetibá,50000\n",
                         encoding="utf-8")
    # Violência doméstica tem uma linha por envolvido: a ocorrência 1 aparece duas vezes.
    vd = pd.DataFrame({
        "ocorrencia": ["1", "1", "2", "3", "4"],
        "data_fato": pd.to_datetime(["2024-02-01", "2024-02-01", "2024-03-05", "2025-10-10", "2025-10-10"]).date,
        "municipio": ["VITORIA", "VITORIA", "VITÓRIA", "VITORIA", "ATLANTIDA"],
    })
    vd.to_parquet(tmp_path / "vd.parquet")
    con = abrir_conexao({"violencia-domestica": tmp_path / "vd.parquet"} | preparar_populacao(populacao, tmp_path / "base"))
    criar_tabela_mapa(con, ["violencia-domestica"])
    return con


def test_conta_ocorrencias_distintas_por_municipio_e_ano_e_ignora_municipio_sem_codigo(con_mapa):
    linhas = con_mapa.execute("SELECT codigo_ibge, ano, ocorrencias FROM mapa_ocorrencias ORDER BY ALL").fetchall()
    assert linhas == [("3205309", 2024, 2), ("3205309", 2025, 1)]


def test_taxa_por_100_mil_inclui_municipio_sem_registro(con_mapa):
    df = taxas(con_mapa, "violencia-domestica", 2024).set_index("municipio")
    assert df.loc["Vitória", "ocorrencias"] == 2
    assert df.loc["Vitória", "taxa"] == pytest.approx(1.0)
    assert df.loc["Santa Maria de Jetibá", "taxa"] == 0


def test_historico_tem_todos_os_anos(con_mapa):
    df = historico(con_mapa, "violencia-domestica", "3205309", [2023, 2024, 2025])
    assert list(df["ano"]) == [2023, 2024, 2025]
    assert list(df["ocorrencias"]) == [0, 2, 1]


def test_classes_por_quantis():
    valores = pd.Series(range(1, 11), dtype=float)
    lims = limites(valores)
    assert lims == pytest.approx([2.8, 4.6, 6.4, 8.2, 10.0])
    assert list(classificar(valores, lims)) == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_quantis_repetidos_viram_uma_classe():
    assert limites(pd.Series([0, 0, 0, 0, 0, 0, 0, 0, 5.0, 10.0])) == pytest.approx([0, 1.0, 10.0])


def test_escala_vai_do_claro_a_cor_do_indicador():
    tons = escala("#7A0177")
    assert len(tons) == 5 and tons[-1] == "#7A0177"


def test_registry_do_mapa_tem_os_16_indicadores():
    indicadores = carregar_mapa(config.ARQUIVO_REGISTRY)
    assert len(indicadores) == 16
    assert {i.grupo for i in indicadores.values()} == {"Crimes contra a vida", "Violência doméstica", "Roubos", "Furtos"}
    # Cada indicador do mapa é calculado a partir da tabela do conjunto de mesmo id.
    assert set(indicadores) <= set(carregar_registry(config.ARQUIVO_REGISTRY))


def test_orienta_contorno_no_sentido_horario():
    quadrado = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]  # anti-horário (RFC 7946)
    malha = {"features": [{"geometry": {"type": "Polygon", "coordinates": [list(quadrado)]}}]}
    anel = orientar(malha)["features"][0]["geometry"]["coordinates"][0]
    assert anel == quadrado[::-1]


def test_malha_do_ibge_fica_no_es_continental():
    with open(config.ARQUIVO_MALHA, encoding="utf-8") as f:
        malha = orientar(sem_ilhas_oceanicas(json.load(f)))
    assert len(malha["features"]) == 78
    lons = [x for f in malha["features"] for p in (f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon"
            else [f["geometry"]["coordinates"]]) for anel in p for x, _ in anel]
    assert -42 < min(lons) and max(lons) < -39


def test_ocorrencias_por_bairro_ignoram_acentos_e_contam_ocorrencias_distintas(con):
    from dominio.mapa import ocorrencias_bairros
    df = ocorrencias_bairros(con, "roubo-celular", "VITORIA", [2024])
    assert dict(zip(df["chave"], df["ocorrencias"])) == {"CENTRO": 2, "JARDIM CAMBURI": 1}


def test_bairros_do_municipio_filtra_pela_malha():
    from dominio.mapa import bairros_do_municipio
    malha = {"features": [{"properties": {"cd_mun": "3205309"}}, {"properties": {"cd_mun": "3205200"}}]}
    assert len(bairros_do_municipio(malha, "3205309")["features"]) == 1
