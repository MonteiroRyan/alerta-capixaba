from conftest import CELULAR, HOMICIDIO
from dominio.consulta import consultar
from dominio.modelos import Intencao


def test_conta_ocorrencias_distintas_rn02(con):
    r = consultar(con, CELULAR, Intencao(no_escopo=True, tipo_crime="roubo-celular"))
    assert r.total == 3
    assert r.agrupado_por == "bairro"
    assert dict(r.grupos) == {"CENTRO": 2, "JARDIM CAMBURI": 1}


def test_filtra_por_bairro_e_agrupa_por_horario(con):
    r = consultar(con, CELULAR, Intencao(no_escopo=True, tipo_crime="roubo-celular", bairro="CENTRO"))
    assert r.total == 2
    assert dict(r.grupos) == {"noite": 1, "manha": 1}


def test_perfil_agrupa_por_sexo(con):
    i = Intencao(no_escopo=True, tipo_crime="homicidios-e-feminicidios", perfil="sexo")
    r = consultar(con, HOMICIDIO, i)
    assert dict(r.grupos) == {"MASCULINO": 6, "FEMININO": 1}


def test_filtra_por_ano(con):
    assert consultar(con, CELULAR, Intencao(no_escopo=True, tipo_crime="roubo-celular", ano=2024)).total == 3
    assert consultar(con, CELULAR, Intencao(no_escopo=True, tipo_crime="roubo-celular", ano=2023)).total == 0


def test_agrupa_pelo_que_a_pergunta_pede(con):
    i = Intencao(no_escopo=True, tipo_crime="roubo-celular", agrupar_por="faixa_horaria")
    assert consultar(con, CELULAR, i).agrupado_por == "faixa_horaria"
