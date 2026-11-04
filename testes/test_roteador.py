import pytest

from conftest import CONJUNTOS
from dados.repositorio import locais
from dominio.modelos import Intencao
from dominio.roteador import RecorteInvalido, rotear


@pytest.fixture
def lugares(con):
    return {cid: locais(con, cid) for cid in CONJUNTOS}


def test_seleciona_conjunto_e_corrige_grafia_do_bairro(lugares):
    i = Intencao(no_escopo=True, tipo_crime="roubo-celular", bairro="jardim  camburí")
    conjunto, i2 = rotear(i, CONJUNTOS, lugares)
    assert conjunto.id == "roubo-celular"
    assert i2.bairro == "JARDIM CAMBURI"


def test_perfil_so_para_crimes_contra_pessoa_rn01(lugares):
    with pytest.raises(RecorteInvalido, match="perfil"):
        rotear(Intencao(no_escopo=True, tipo_crime="roubo-celular", perfil="sexo"), CONJUNTOS, lugares)
    conjunto, _ = rotear(Intencao(no_escopo=True, tipo_crime="homicidios-e-feminicidios", perfil="sexo"),
                         CONJUNTOS, lugares)
    assert conjunto.tem_perfil


def test_tipo_desconhecido_e_bairro_inexistente(lugares):
    with pytest.raises(RecorteInvalido):
        rotear(Intencao(no_escopo=True, tipo_crime="furto-de-bicicleta"), CONJUNTOS, lugares)
    with pytest.raises(RecorteInvalido, match="bairro"):
        rotear(Intencao(no_escopo=True, tipo_crime="roubo-celular", bairro="ATLANTIDA"), CONJUNTOS, lugares)


def test_ano_fora_da_base(lugares):
    with pytest.raises(RecorteInvalido, match="2024 a 2024"):
        rotear(Intencao(no_escopo=True, tipo_crime="roubo-celular", ano=2026), CONJUNTOS, lugares)


@pytest.mark.parametrize("estado", ["ES", "es", "Espírito Santo"])
def test_es_como_municipio_vira_o_estado_todo(lugares, estado):
    i = Intencao(no_escopo=True, tipo_crime="homicidios-e-feminicidios", municipio=estado, perfil="cor_raca")
    _, i2 = rotear(i, CONJUNTOS, lugares)
    assert i2.municipio is None
