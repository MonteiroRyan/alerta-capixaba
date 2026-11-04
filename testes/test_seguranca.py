import json

import pytest
from pydantic import ValidationError

from conftest import CONJUNTOS
from dominio.modelos import Intencao
from dominio.orquestrador import Orquestrador
from infra import config
from infra.limites import LimiteSessao, TetoGlobal


class ClienteFalso:
    def __init__(self, intencao: dict):
        self.intencao = intencao

    def gerar_json(self, instrucao, texto, schema):
        return json.dumps(self.intencao)

    def gerar_texto(self, instrucao, texto):
        return "resposta redigida"


def test_rejeita_intencao_fora_do_schema():
    with pytest.raises(ValidationError):
        Intencao.model_validate({"no_escopo": True, "faixa_horaria": "meia-noite"})


def test_injecao_no_bairro_nao_chega_ao_sql(con):
    intencao = {"no_escopo": True, "tipo_crime": "roubo-celular", "bairro": "CENTRO' OR '1'='1"}
    r = Orquestrador(con, CONJUNTOS, ClienteFalso(intencao)).responder("roubos no centro")
    assert r.resultado is None
    assert "Não encontrei" in r.texto


def test_duckdb_sem_acesso_externo(con):
    with pytest.raises(Exception):
        con.execute("SELECT * FROM read_csv('requirements.txt')")
    with pytest.raises(Exception):
        con.execute("SET enable_external_access = true")


def test_limite_de_caracteres_e_fluxo_completo(con):
    intencao = {"no_escopo": True, "tipo_crime": "roubo-celular", "bairro": "centro"}
    o = Orquestrador(con, CONJUNTOS, ClienteFalso(intencao))
    assert "caracteres" in o.responder("x" * (config.MAX_CARACTERES + 1)).texto
    r = o.responder("roubos de celular no centro")
    assert r.texto == "resposta redigida"
    assert r.resultado.total == 2


def test_limites_de_uso():
    s = LimiteSessao(2)
    assert s.permitir(0) and s.permitir(1) and not s.permitir(2)
    assert s.permitir(61)
    t = TetoGlobal(1)
    assert t.permitir() and not t.permitir()


def test_cursor_por_sessao_mantem_acesso_externo_bloqueado(con):
    cur = con.cursor()
    assert cur.execute('SELECT COUNT(*) FROM "roubo-celular"').fetchone()[0] == 4
    with pytest.raises(Exception):
        cur.execute("SELECT * FROM read_csv('requirements.txt')")
