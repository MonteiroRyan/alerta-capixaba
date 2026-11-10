import json
import logging
import os
from datetime import datetime

import streamlit as st

from dados.ingestao import obter_csvs, preparar_base, preparar_populacao
from dados.registry import IndicadorMapa, carregar_mapa, carregar_registry
from dados.repositorio import abrir_conexao
from dominio.mapa import criar_tabela_mapa, orientar, sem_ilhas_oceanicas
from dominio.orquestrador import Orquestrador
from infra import config
from infra.gemini_cliente import ClienteGemini
from infra.limites import LimiteSessao, TetoGlobal
from ui.base import aplicar_estilo, barra_lateral, cabecalho
from ui.chat import conversa
from ui.mapa import mapa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def segredo(nome: str) -> str | None:
    try:
        return st.secrets[nome]
    except Exception:
        return os.environ.get(nome)


@st.cache_resource(ttl=config.TTL_CACHE_S, show_spinner="Preparando os dados da SESP-ES…")
def carregar() -> tuple[Orquestrador, dict, datetime]:
    conjuntos = carregar_registry(config.ARQUIVO_REGISTRY)
    obter_csvs(conjuntos, config.DIR_DOWNLOAD, config.DIR_CSV, config.TTL_CACHE_S)
    parquets = preparar_base(conjuntos, config.DIR_DOWNLOAD, config.DIR_BASE)
    conjuntos = {cid: c for cid, c in conjuntos.items() if cid in parquets}
    con = abrir_conexao(parquets | preparar_populacao(config.ARQUIVO_POPULACAO, config.DIR_BASE))
    criar_tabela_mapa(con, [i for i in carregar_mapa(config.ARQUIVO_REGISTRY) if i in conjuntos])
    chave_api = segredo("GEMINI_API_KEY")
    if not chave_api:
        log.warning("GEMINI_API_KEY ausente: preencha .streamlit/secrets.toml para ativar o assistente")
    cliente = ClienteGemini(chave_api, segredo("GEMINI_MODELO") or config.MODELO_GEMINI) if chave_api else None
    orquestrador = Orquestrador(con, conjuntos, cliente)
    return orquestrador, orquestrador.cobertura(), datetime.now()


@st.cache_resource
def teto_global() -> TetoGlobal:
    return TetoGlobal(config.TETO_GLOBAL_POR_DIA)


@st.cache_resource
def dados_mapa() -> tuple[dict[str, IndicadorMapa], dict, dict]:
    with open(config.ARQUIVO_MALHA, encoding="utf-8") as f:
        malha = orientar(sem_ilhas_oceanicas(json.load(f)))
    with open(config.ARQUIVO_MALHA_BAIRROS, encoding="utf-8") as f:
        malha_bairros = orientar(json.load(f))
    return carregar_mapa(config.ARQUIVO_REGISTRY), malha, malha_bairros


st.set_page_config(page_title="Alerta Capixaba", page_icon=":material/shield:", layout="wide",
                   initial_sidebar_state="auto")
aplicar_estilo()
st.session_state.setdefault("historico", [])
st.session_state.setdefault("limite", LimiteSessao(config.MAX_PERGUNTAS_POR_MINUTO))

orquestrador, cobertura, carregado_em = carregar()
indicadores, malha, malha_bairros = dados_mapa()
indicadores = {iid: ind for iid, ind in indicadores.items() if iid in orquestrador.conjuntos}

barra_lateral(orquestrador, cobertura, carregado_em)
cabecalho(cobertura)

with st.container(key="painel"):
    coluna_chat, coluna_mapa = st.columns(2, gap="large")

with coluna_mapa:
    mapa(orquestrador.con.cursor(), indicadores, malha, malha_bairros)

with coluna_chat.container(key="coluna-chat"):
    conversa(orquestrador, teto_global())
