"""Cada ramo do fluxo da interface (seção 4 da especificação) devolve o tipo e as saídas certas."""
from conftest import CONJUNTOS
from dominio.orquestrador import Orquestrador
from test_seguranca import ClienteFalso


class ClienteQueFalha(ClienteFalso):
    def gerar_json(self, instrucao, texto, schema):
        raise RuntimeError("503")


def responder(con, intencao, pergunta="pergunta"):
    return Orquestrador(con, CONJUNTOS, ClienteFalso(intencao)).responder(pergunta)


def test_resposta_com_dados_traz_continuacoes(con):
    r = responder(con, {"no_escopo": True, "tipo_crime": "homicidios-e-feminicidios", "municipio": "vitoria"})
    assert r.tipo == "resposta"
    assert r.conjunto.id == "homicidios-e-feminicidios"
    assert any("por sexo" in o for o in r.opcoes)


def test_fora_do_escopo_sugere_perguntas(con):
    r = responder(con, {"no_escopo": False})
    assert r.tipo == "fora_escopo"
    assert r.texto.startswith("Respondo só perguntas sobre estatísticas criminais")
    assert r.opcoes


def test_tipo_vago_oferece_os_conjuntos(con):
    r = responder(con, {"no_escopo": True}, "roubos em 2024")
    assert r.tipo == "esclarecimento"
    assert r.opcoes == ["Roubo de celular no ES"]  # "roubos" filtra os conjuntos de roubo


def test_perfil_indisponivel_oferece_recorte_valido(con):
    r = responder(con, {"no_escopo": True, "tipo_crime": "roubo-celular", "perfil": "sexo"})
    assert r.tipo == "esclarecimento"
    assert r.opcoes == ["Roubo de celular no ES"]


def test_servico_indisponivel_vira_erro(con):
    r = Orquestrador(con, CONJUNTOS, ClienteQueFalha({})).responder("homicídios em Serra")
    assert r.tipo == "erro"
    assert "Sua pergunta foi mantida" in r.texto


def test_pergunta_sobre_o_es_traz_dados_e_grafico(con):
    # Regressão: o interpretador devolvia municipio="ES" e a resposta virava "Não encontrei o município".
    r = responder(con, {"no_escopo": True, "tipo_crime": "homicidios-e-feminicidios", "municipio": "ES",
                        "ano": 2024, "perfil": "sexo"})
    assert r.tipo == "resposta"
    assert r.resultado.grupos
    assert "municipio" not in r.resultado.filtros


def test_tipo_vago_filtra_pela_palavra_usada():
    from dados.registry import ConjuntoDados
    from dominio.sugestoes import candidatos
    conjuntos = {cid: ConjuntoDados(cid, cid, "A", "", "", {}) for cid in
                 ("roubo-celular", "roubo-a-pessoa", "furto-celular", "violencia-domestica")}
    assert [c.id for c in candidatos("quantos assaltos em Vitória?", conjuntos)] == ["roubo-celular", "roubo-a-pessoa"]
    assert [c.id for c in candidatos("e os furtos?", conjuntos)] == ["furto-celular"]
    assert len(candidatos("crimes em Serra", conjuntos)) == 4
