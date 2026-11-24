import pytest

from conftest import CONJUNTOS
from dados.repositorio import locais
from dominio.interpretador import schema_intencao
from dominio.modelos import Intencao, ResultadoConsulta
from dominio.orquestrador import Orquestrador
from dominio.resposta import numeros_conferem, redigir
from dominio.roteador import RecorteInvalido, rotear, unificar
from test_seguranca import ClienteFalso

COMPARACAO = ResultadoConsulta("Roubo de veículo", 1216, "ano", [("2023", 489), ("2024", 392), ("2025", 335)],
                               ("01/01/2023", "29/12/2025"), {"municipio": "VILA VELHA", "anos": "2023, 2024, 2025"})
TAXA = ResultadoConsulta("Homicídios e feminicídios", 92, "bairro", [("CENTRO", 8)], ("03/01/2025", "28/12/2025"),
                         {"municipio": "SERRA", "ano": "2025"}, medida="taxa", taxa_total=17.67)


class ClienteRedator(ClienteFalso):
    def __init__(self, texto):
        super().__init__({})
        self.texto = texto

    def gerar_texto(self, instrucao, texto):
        return self.texto


@pytest.fixture
def lugares(con):
    return {cid: locais(con, cid) for cid in CONJUNTOS}


def test_schema_pede_medida_anos_e_municipios():
    schema = schema_intencao(CONJUNTOS)
    assert {"medida", "anos", "municipios"} <= set(schema["required"])
    assert "municipio" in schema["properties"]["agrupar_por"]["anyOf"][0]["enum"]


def test_lista_com_um_so_item_vira_campo_simples():
    i = unificar(Intencao(no_escopo=True, municipios=["Vitória"], anos=[2024]))
    assert (i.municipio, i.municipios, i.ano, i.anos) == ("Vitória", [], 2024, [])


def test_comparacao_define_o_agrupamento():
    assert unificar(Intencao(no_escopo=True, municipios=["Vitória", "Serra"])).agrupar_por == "municipio"
    assert unificar(Intencao(no_escopo=True, ano=2023, anos=[2025])).agrupar_por == "ano"


@pytest.mark.parametrize("recorte", [{"bairro": "CENTRO"}, {"agrupar_por": "faixa_horaria"}, {"faixa_horaria": "noite"}])
def test_taxa_sem_populacao_e_recusada_com_motivo(lugares, recorte):
    i = Intencao(no_escopo=True, tipo_crime="roubo-celular", medida="taxa", **recorte)
    with pytest.raises(RecorteInvalido, match="100 mil") as erro:
        rotear(i, CONJUNTOS, lugares)
    assert erro.value.motivo == "taxa"


def test_taxa_sem_ano_usa_o_ultimo_ano(lugares):
    _, i = rotear(Intencao(no_escopo=True, tipo_crime="roubo-celular", medida="taxa"), CONJUNTOS, lugares)
    assert i.ano == 2024


def test_municipio_da_comparacao_e_validado(lugares):
    i = Intencao(no_escopo=True, tipo_crime="roubo-celular", municipios=["Vitória", "Atlântida"])
    with pytest.raises(RecorteInvalido, match="Atlântida"):
        rotear(i, CONJUNTOS, lugares)


def test_recusa_de_taxa_oferece_a_contagem(con):
    intencao = {"no_escopo": True, "tipo_crime": "roubo-celular", "bairro": "centro", "medida": "taxa"}
    r = Orquestrador(con, CONJUNTOS, ClienteFalso(intencao)).responder("taxa de roubo no centro")
    assert r.tipo == "esclarecimento"
    assert "mapa" in r.texto
    assert r.opcoes == ["Roubo de celular no bairro Centro"]


def test_numeros_do_resultado_sao_aceitos():
    texto = "Em Vila Velha foram **489** roubos de veículo em 2023, 392 em 2024 e 335 em 2025; o número diminuiu."
    assert numeros_conferem(texto, COMPARACAO)
    assert numeros_conferem("A taxa foi de **17,7 por 100 mil habitantes** (Censo 2022), com 92 casos.", TAXA)


@pytest.mark.parametrize("texto", [
    "Os roubos caíram 31,5% de 2023 para 2025.",  # percentual calculado pelo modelo
    "Foram 1.300 roubos no período.",  # total inventado
    "A taxa foi de 17,6 por 100 mil habitantes.",  # arredondamento diferente
])
def test_numero_fora_do_resultado_e_barrado(texto):
    assert not numeros_conferem(texto, COMPARACAO if "roubos" in texto else TAXA)


def test_redacao_com_numero_inventado_usa_o_texto_padrao():
    texto = redigir(ClienteRedator("Os roubos caíram 31,5% de 2023 para 2025."), COMPARACAO)
    assert "31,5" not in texto
    assert "489" in texto and "diminuiu" in texto
