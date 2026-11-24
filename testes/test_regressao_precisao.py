"""Regressão do teste de precisão (20 perguntas, Apêndice A do artigo).

Cada caso usa a cópia dos dados em dataset/ (a mesma do teste de 8/11/2026) e a intenção
que o modelo deveria extrair da pergunta. O cliente simulado substitui o Gemini, de modo
que o teste verifica tudo o que vem depois da interpretação: roteamento, consulta, taxa,
privacidade e o texto final. As perguntas 9 a 13 e 15 falhavam na versão avaliada.
"""
import pytest

from dados.ingestao import preparar_base, preparar_populacao
from dados.registry import carregar_registry
from dados.repositorio import abrir_conexao
from dominio.orquestrador import Orquestrador
from dominio.resposta import NUMERO
from infra import config
from test_seguranca import ClienteFalso

USADOS = ["roubo-celular", "furto-de-veiculo", "homicidios-e-feminicidios", "violencia-domestica",
          "roubo-em-transporte-coletivo", "furto-de-bicicleta", "roubo-a-pessoa", "furto-em-residencia",
          "roubo-de-veiculo", "furto-celular"]


class ClienteSemRedacao(ClienteFalso):
    """Devolve a intenção combinada e usa o texto padrão do sistema na resposta."""

    def gerar_texto(self, instrucao, texto):
        raise RuntimeError("sem redação")


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    if not (config.DIR_CSV / "roubo-celular.csv").exists():
        pytest.skip("dataset/ indisponível")
    destino = tmp_path_factory.mktemp("base")
    conjuntos = {cid: c for cid, c in carregar_registry(config.ARQUIVO_REGISTRY).items() if cid in USADOS}
    parquets = preparar_base(conjuntos, config.DIR_CSV, destino)
    con = abrir_conexao(parquets | preparar_populacao(config.ARQUIVO_POPULACAO, destino))
    return con, conjuntos


def perguntar(base, intencao, pergunta="pergunta"):
    con, conjuntos = base
    return Orquestrador(con, conjuntos, ClienteSemRedacao({"no_escopo": True} | intencao)).responder(pergunta)


def numeros(texto):
    return NUMERO.findall(texto)


CONTAGENS = [
    (1, {"tipo_crime": "roubo-celular", "municipio": "Vitória", "ano": 2025}, 900),
    (2, {"tipo_crime": "furto-de-veiculo", "municipio": "Vila Velha", "ano": 2024}, 556),
    (3, {"tipo_crime": "homicidios-e-feminicidios", "municipio": "Cariacica", "ano": 2023}, 106),
    (4, {"tipo_crime": "violencia-domestica", "municipio": "Serra", "ano": 2025}, 2902),
    (5, {"tipo_crime": "roubo-em-transporte-coletivo", "municipio": "Cariacica", "ano": 2023}, 356),
    (6, {"tipo_crime": "furto-de-bicicleta", "municipio": "Linhares", "ano": 2024}, 150),
    (7, {"tipo_crime": "roubo-a-pessoa", "municipio": "Divino de São Lourenço", "ano": 2025}, 1),
    (8, {"tipo_crime": "furto-em-residencia", "ano": 2024}, 4442),
]


@pytest.mark.parametrize("n, intencao, esperado", CONTAGENS, ids=[f"p{c[0]}" for c in CONTAGENS])
def test_contagens(base, n, intencao, esperado):
    r = perguntar(base, intencao)
    assert r.tipo == "resposta"
    assert r.resultado.total == esperado
    assert f"{esperado:,}".replace(",", ".") in r.texto


TAXAS = [
    (9, {"tipo_crime": "homicidios-e-feminicidios", "municipio": "Serra", "ano": 2025}, 92, "17,7"),
    (10, {"tipo_crime": "roubo-celular", "municipio": "Vitória", "ano": 2024}, 1558, "482,5"),
    (11, {"tipo_crime": "violencia-domestica", "municipio": "Colatina", "ano": 2025}, 1142, "951,4"),
]


@pytest.mark.parametrize("n, intencao, total, taxa", TAXAS, ids=[f"p{c[0]}" for c in TAXAS])
def test_taxa_por_100_mil(base, n, intencao, total, taxa):
    r = perguntar(base, intencao | {"medida": "taxa"})
    assert r.tipo == "resposta"
    assert r.resultado.total == total
    assert f"{r.resultado.taxa_total:.1f}".replace(".", ",") == taxa
    assert taxa in r.texto and "100 mil" in r.texto


def test_p12_comparacao_entre_anos(base):
    r = perguntar(base, {"tipo_crime": "roubo-de-veiculo", "municipio": "Vila Velha",
                         "anos": [2023, 2024, 2025], "agrupar_por": "ano"})
    assert r.tipo == "resposta"
    assert dict(r.resultado.grupos) == {"2023": 489, "2024": 392, "2025": 335}
    assert [g for g, _ in r.resultado.grupos] == ["2023", "2024", "2025"]
    assert "diminuiu" in r.texto
    assert {"489", "392", "335"} <= set(numeros(r.texto))


def test_p13_comparacao_entre_municipios(base):
    r = perguntar(base, {"tipo_crime": "furto-celular", "municipios": ["Vitória", "Vila Velha"],
                         "ano": 2025, "agrupar_por": "municipio"})
    assert r.tipo == "resposta"
    assert dict(r.resultado.grupos) == {"Vitória": 1834, "Vila Velha": 1221}
    assert r.resultado.total == 1834 + 1221
    assert "1.834" in r.texto and "1.221" in r.texto


def test_p14_ranking_de_bairros(base):
    r = perguntar(base, {"tipo_crime": "violencia-domestica", "municipio": "Serra", "ano": 2025,
                         "agrupar_por": "bairro"})
    assert r.resultado.grupos[:3] == [("FEU ROSA", 128), ("BAIRRO DAS LARANJEIRAS", 127),
                                      ("VILA NOVA DE COLARES", 124)]


def test_p15_ranking_de_municipios_pela_taxa(base):
    r = perguntar(base, {"tipo_crime": "homicidios-e-feminicidios", "ano": 2025, "agrupar_por": "municipio",
                         "medida": "taxa"})
    assert r.tipo == "resposta"
    primeiro, ocorrencias = r.resultado.grupos[0]
    assert (primeiro, ocorrencias) == ("Jaguaré", 17)
    assert f"{r.resultado.taxas[primeiro]:.1f}" == "58.8"
    assert "Jaguaré" in r.texto and "58,8" in r.texto


def test_p16_faixa_horaria(base):
    r = perguntar(base, {"tipo_crime": "roubo-celular", "municipio": "Vitória", "agrupar_por": "faixa_horaria"})
    assert r.resultado.total == 4142
    assert r.resultado.grupos[0] == ("noite", 1796)


def test_p17_perfil_com_supressao(base):
    r = perguntar(base, {"tipo_crime": "homicidios-e-feminicidios", "municipio": "Cariacica", "ano": 2024,
                         "perfil": "idade"})
    assert r.resultado.grupos[:3] == [("18 a 24", 29), ("25 a 34", 24), ("35 a 44", 18)]
    assert r.resultado.suprimidos > 0


def test_p18_fora_do_escopo(base):
    con, conjuntos = base
    r = Orquestrador(con, conjuntos, ClienteSemRedacao({"no_escopo": False})).responder("melhor bairro")
    assert r.tipo == "fora_escopo"


def test_p19_tipo_ambiguo_pede_esclarecimento(base):
    r = perguntar(base, {"municipio": "Vitória"}, "Quantos roubos teve em Vitória?")
    assert r.tipo == "esclarecimento"


def test_p20_ano_fora_da_base(base):
    r = perguntar(base, {"tipo_crime": "homicidios-e-feminicidios", "municipio": "Vila Velha", "ano": 2020})
    assert r.tipo == "esclarecimento"
    assert "2023 a 2025" in r.texto
