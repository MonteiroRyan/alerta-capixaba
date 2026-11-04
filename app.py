import json
import logging
import os
from datetime import datetime

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dados.ingestao import obter_csvs, preparar_base, preparar_populacao
from dados.registry import IndicadorMapa, carregar_mapa, carregar_registry
from dados.repositorio import abrir_conexao, chave
from dominio.mapa import (bairros_do_municipio, classificar, criar_tabela_mapa, escala, historico, limites,
                          ocorrencias_bairros,
                          orientar, sem_ilhas_oceanicas, taxas)
from dominio.orquestrador import Orquestrador, Resposta
from dominio.resposta import ROTULOS, formatar_nome, legivel
from dominio.sugestoes import EXEMPLOS, FAIXAS, PERFIS
from infra import avaliacoes, config
from infra.gemini_cliente import ClienteGemini
from infra.limites import LimiteSessao, TetoGlobal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

AVISO_IA = "As respostas são geradas por IA e podem conter erros. Confira a fonte indicada em cada resposta."
PORTAL = "https://dados.es.gov.br/organization/sesp"
ANOS_MAPA = [2023, 2024, 2025]
ALTURA_MAPA = 520
CONFIG_MAPA = {"scrollZoom": True, "displayModeBar": True, "displaylogo": False,
               "modeBarButtons": [["zoomInGeo", "zoomOutGeo", "resetGeo"]]}

ARQUIVO_CSS = config.RAIZ / "styles.css"
LOGO = config.RAIZ / "static" / "logo-alerta-capixaba.png"


def segredo(nome: str) -> str | None:
    try:
        return st.secrets[nome]
    except Exception:
        return os.environ.get(nome)


@st.cache_resource(ttl=config.TTL_CACHE_S, show_spinner="Preparando os dados da SESP-ES…")
def carregar() -> tuple[Orquestrador, datetime]:
    conjuntos = carregar_registry(config.ARQUIVO_REGISTRY)
    obter_csvs(conjuntos, config.DIR_DOWNLOAD, config.DIR_CSV, config.TTL_CACHE_S)
    parquets = preparar_base(conjuntos, config.DIR_DOWNLOAD, config.DIR_BASE)
    conjuntos = {cid: c for cid, c in conjuntos.items() if cid in parquets}
    con = abrir_conexao(parquets | preparar_populacao(config.ARQUIVO_POPULACAO, config.DIR_BASE))
    criar_tabela_mapa(con, [i for i in carregar_mapa(config.ARQUIVO_REGISTRY) if i in conjuntos])
    chave_api = segredo("GEMINI_API_KEY")
    cliente = ClienteGemini(chave_api, segredo("GEMINI_MODELO") or config.MODELO_GEMINI) if chave_api else None
    return Orquestrador(con, conjuntos, cliente), datetime.now()


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


def perguntar(texto: str) -> None:
    st.session_state.pendente = texto


def nova_conversa() -> None:
    st.session_state.historico = []


def ao_escolher(chave: str) -> None:
    if escolha := st.session_state.get(chave):
        perguntar(escolha)


def preencher_chat(texto: str) -> None:
    st.session_state.entrada = texto


def ver_bairros(codigo: str, nome: str) -> None:
    st.session_state.mapa_municipio = (codigo, nome)
    st.session_state.pop("mapa", None)


def voltar_ao_estado() -> None:
    st.session_state.mapa_municipio = None
    st.session_state.pop("mapa", None)


def ao_avaliar(chave: str, pergunta: str, resposta: str) -> None:
    valor = st.session_state.get(chave)
    if valor is not None:
        avaliacoes.registrar(config.ARQUIVO_AVALIACOES, pergunta, resposta, util=valor == 1)


def barra_lateral(orquestrador: Orquestrador, carregado_em: datetime) -> None:
    with st.sidebar:
        st.image(str(LOGO), width=180)
        st.caption("Dados de segurança pública do Espírito Santo")
        st.button("Nova conversa", icon=":material/add:", on_click=nova_conversa, width="stretch")

        perguntas = [m["texto"] for m in st.session_state.historico if m["papel"] == "user"]
        if perguntas:
            st.subheader("Nesta sessão")
            for p in reversed(perguntas[-8:]):
                st.markdown(f"- {p}")

        st.subheader("Sobre os dados")
        cobertura = orquestrador.cobertura()
        inicio, fim = cobertura["anos"]
        st.markdown(
            f"Fonte: [SESP-ES, dados abertos]({PORTAL})  \n"
            f"Cobertura: {cobertura['municipios']} municípios, de {inicio} a {fim}  \n"
            f"Atualizado em: {carregado_em:%d/%m/%Y}"
        )
        with st.expander("Ver indicadores disponíveis"):
            for c in orquestrador.conjuntos.values():
                detalhe = "por local, horário e perfil da vítima" if c.tem_perfil else "por local e horário"
                st.markdown(f"[{c.nome}]({c.url}): {detalhe}")

        st.subheader("Aviso")
        st.markdown("Este site não registra ocorrências. Em emergência, ligue **190**.")


def boas_vindas() -> None:
    st.title("Pergunte sobre a segurança pública no Espírito Santo")
    st.markdown("Respostas baseadas nos dados abertos da Secretaria de Segurança Pública (SESP-ES). "
                "Pergunte do jeito que você falaria.")
    st.caption("EXPERIMENTE PERGUNTAR")
    colunas = st.columns(2)
    for i, (pergunta, tipo) in enumerate(EXEMPLOS):
        with colunas[i % 2]:
            st.button(f"{pergunta}  \n:gray[{tipo}]", key=f"exemplo{i}", on_click=perguntar,
                      args=(pergunta,), width="stretch", wrap=True)


def como_entendi(r: Resposta) -> None:
    i = r.intencao
    filtros = [("Indicador", r.conjunto.nome)]
    if i.municipio:
        filtros.append(("Município", formatar_nome(i.municipio)))
    if i.bairro:
        filtros.append(("Bairro", formatar_nome(i.bairro)))
    filtros.append(("Período", str(i.ano) if i.ano else "todo o período"))
    if i.faixa_horaria:
        filtros.append(("Horário", FAIXAS[i.faixa_horaria]))
    if i.perfil:
        filtros.append(("Perfil", PERFIS[i.perfil]))
    with st.expander("Como entendi sua pergunta"):
        st.markdown(" ".join(f":blue-background[{rotulo}: **{valor}**]" for rotulo, valor in filtros))
        st.caption(f"Consulta feita em {r.consultado_em:%d/%m/%Y, %H:%M}. "
                   "Algo errado? Reformule a pergunta com mais detalhes.")


def grafico(df: pd.DataFrame, rotulo: str) -> alt.Chart:
    return alt.Chart(df).mark_bar(color=config.COR_PRIMARIA, cornerRadiusEnd=3).encode(
        x=alt.X("Ocorrências:Q", title="Ocorrências", axis=alt.Axis(format="d")),
        y=alt.Y(f"{rotulo}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        tooltip=[rotulo, "Ocorrências"],
    ).properties(height=28 * len(df) + 40)


def resposta_com_dados(r: Resposta, indice: int, pergunta: str) -> None:
    st.markdown(r.texto)
    resultado = legivel(r.resultado)
    if resultado.grupos:
        rotulo = ROTULOS[resultado.agrupado_por].capitalize()
        df = pd.DataFrame(resultado.grupos, columns=[rotulo, "Ocorrências"])
        st.altair_chart(grafico(df, rotulo))

    st.markdown(f"Fonte: SESP-ES, dados abertos · indicador \"{r.conjunto.nome}\"  \n"
                f"[Abrir conjunto de dados]({r.conjunto.url})")
    como_entendi(r)

    acoes = st.columns([1, 1, 2], vertical_alignment="center")
    if resultado.grupos:
        with acoes[0].popover("Ver tabela"):
            st.dataframe(df, hide_index=True)
        acoes[1].download_button("Baixar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                                 file_name="alerta-capixaba.csv", mime="text/csv", key=f"csv{indice}")
    with acoes[2]:
        st.caption("A resposta foi útil?")
        chave = f"avaliacao{indice}"
        st.feedback("thumbs", key=chave, on_change=ao_avaliar, args=(chave, pergunta, r.texto))


def sugestoes(r: Resposta, indice: int) -> None:
    if r.opcoes:
        chave = f"sugestao{indice}"
        st.pills("Sugestões", r.opcoes, key=chave, on_change=ao_escolher, args=(chave,),
                 label_visibility="collapsed")


def mensagem(m: dict, indice: int) -> None:
    if m["papel"] == "user":
        with st.chat_message("user"):
            st.markdown(m["texto"])
        return
    r: Resposta = m["resposta"]
    with st.chat_message("assistant"):
        if r.tipo == "resposta":
            resposta_com_dados(r, indice, m["pergunta"])
        elif r.tipo == "erro":
            with st.container(border=True):
                st.error(r.texto, icon=":material/error:")
                st.button("Tentar novamente", type="primary", key=f"repetir{indice}",
                          on_click=perguntar, args=(m["pergunta"],))
        else:
            st.markdown(r.texto)
        sugestoes(r, indice)


def responder(orquestrador: Orquestrador, pergunta: str) -> Resposta:
    if not st.session_state.limite.permitir():
        return Resposta("Você fez muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo.", "aviso")
    if not teto_global().permitir():
        return Resposta("O limite diário de perguntas foi atingido. Tente de novo amanhã.", "aviso")
    return orquestrador.responder(pergunta)


def numero(valor: float, casas: int = 1) -> str:
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def rotulo_indicador(ind: IndicadorMapa) -> str:
    return ind.nome if ind.nome == ind.grupo else f"{ind.grupo} › {ind.nome}"


def figura_mapa(malha: dict, idkey: str, ids: pd.Series, classes, cores: list[str],
                nomes: pd.Series, valores: pd.Series, unidade: str, revisao: str) -> go.Figure:
    k = len(cores)
    degraus = [[pos, c] for i, c in enumerate(cores) for pos in (i / k, (i + 1) / k)]
    fig = go.Figure(go.Choropleth(
        geojson=malha, featureidkey=f"properties.{idkey}", locations=ids,
        z=classes + 0.5, zmin=0, zmax=k, colorscale=degraus, showscale=False,
        marker_line=dict(color="#6B7785", width=0.5),
        customdata=list(zip(nomes, valores)),
        hovertemplate=f"<b>%{{customdata[0]}}</b><br>%{{customdata[1]}} {unidade}<extra></extra>",
        unselected=dict(marker=dict(opacity=0.45)),
    ))
    fig.update_geos(fitbounds="locations", projection_type="mercator", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=ALTURA_MAPA, dragmode="pan", uirevision=revisao,
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def cores_das_classes(cor: str, k: int) -> list[str]:
    tons = escala(cor)
    return [tons[round(i * (len(tons) - 1) / (k - 1))] for i in range(k)] if k > 1 else tons[:1]


def legenda(lims: list[float], cores: list[str], nota: str, casas: int = 1) -> None:
    itens = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:14px;white-space:nowrap">'
        f'<span style="width:14px;height:14px;background:{c};border:1px solid #6B7785;border-radius:2px"></span>'
        f"{'sem registro' if l == 0 else 'até ' + numero(l, casas)}</span>"
        for l, c in zip(lims, cores)
    )
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;row-gap:4px;font-size:0.9rem">{itens}</div>',
                unsafe_allow_html=True)
    st.caption(nota)


def painel_municipio(con, ind: IndicadorMapa, codigo: str, nome: str, ano: int, tem_bairros: bool) -> None:
    df = historico(con, ind.id, codigo, ANOS_MAPA)
    with st.container(border=True):
        st.subheader(nome)
        st.caption(ind.nome)
        st.dataframe(pd.DataFrame({
            "Ano": df["ano"].astype(str),
            "Taxa por 100 mil hab.": df["taxa"].map(numero),
            "Ocorrências": df["ocorrencias"].map(lambda n: numero(n, 0)),
        }), hide_index=True)
        pergunta = f"Quantos casos de {ind.nome.lower()} houve em {nome} em {ano}?"
        acoes = st.columns(2) if tem_bairros else [st.container()]
        acoes[0].button("Perguntar sobre este município", icon=":material/chat:", on_click=preencher_chat,
                        args=(pergunta,), width="stretch")
        if tem_bairros:
            acoes[1].button("Ver bairros", icon=":material/map:", on_click=ver_bairros, args=(codigo, nome),
                            width="stretch")
        else:
            st.caption("O IBGE não publica a divisão oficial de bairros deste município.")


def painel_bairro(ind: IndicadorMapa, nome: str, municipio: str, anos: pd.DataFrame, ano: int) -> None:
    with st.container(border=True):
        st.subheader(nome)
        st.caption(f"{ind.nome} · {municipio}")
        st.dataframe(pd.DataFrame({"Ano": anos["ano"].astype(str),
                                   "Ocorrências": anos["ocorrencias"].map(lambda n: numero(n, 0))}),
                     hide_index=True)
        pergunta = f"Quantos casos de {ind.nome.lower()} houve no bairro {nome} em {municipio} em {ano}?"
        st.button("Perguntar sobre este bairro", icon=":material/chat:", on_click=preencher_chat,
                  args=(pergunta,), width="stretch")


def selecionado(evento, ids: pd.Series) -> str | None:
    pontos = evento.selection.points
    if not pontos:
        return None
    return pontos[0].get("location") or ids.iloc[pontos[0]["point_index"]]


def mapa_estado(con, ind: IndicadorMapa, ano: int, malha: dict, com_bairros: set[str]) -> None:
    df = taxas(con, ind.id, ano)
    lims = limites(df["taxa"])
    cores = cores_das_classes(ind.cor, len(lims))
    fig = figura_mapa(malha, "codarea", df["codigo_ibge"], classificar(df["taxa"], lims), cores,
                      df["municipio"], df["taxa"].map(numero), "por 100 mil hab.", "estado")
    with st.container(key="caixa-mapa"):
        evento = st.plotly_chart(fig, key="mapa", on_select="rerun", selection_mode="points", config=CONFIG_MAPA)
    legenda(lims, cores, "Ocorrências por 100 mil habitantes (população do Censo 2022, IBGE).")

    if codigo := selecionado(evento, df["codigo_ibge"]):
        nome = df.loc[df["codigo_ibge"] == codigo, "municipio"].iloc[0]
        painel_municipio(con, ind, codigo, nome, ano, codigo in com_bairros)
    else:
        st.caption("Clique em um município para ver a taxa, as ocorrências de 2023 a 2025 e, "
                   "quando houver, o mapa por bairro.")


def mapa_bairros(con, ind: IndicadorMapa, ano: int, codigo: str, municipio: str, malha_bairros: dict) -> None:
    st.button("Voltar ao mapa do estado", icon=":material/arrow_back:", on_click=voltar_ao_estado)
    recorte = bairros_do_municipio(malha_bairros, codigo)
    df = pd.DataFrame([f["properties"] for f in recorte["features"]])
    df["chave"] = df["nome"].map(chave)
    contagens = ocorrencias_bairros(con, ind.id, chave(municipio), ANOS_MAPA)
    no_ano = contagens[contagens["ano"] == ano]
    df = df.merge(no_ano[["chave", "ocorrencias"]], on="chave", how="left").fillna({"ocorrencias": 0})

    lims = limites(df["ocorrencias"])
    cores = cores_das_classes(ind.cor, len(lims))
    fig = figura_mapa(recorte, "cd_bairro", df["cd_bairro"], classificar(df["ocorrencias"], lims), cores,
                      df["nome"], df["ocorrencias"].map(lambda n: numero(n, 0)), "ocorrências", f"bairros-{codigo}")
    with st.container(key="caixa-mapa"):
        evento = st.plotly_chart(fig, key="mapa", on_select="rerun", selection_mode="points", config=CONFIG_MAPA)

    total = int(no_ano["ocorrencias"].sum())
    casadas = int(no_ano.loc[no_ano["chave"].isin(df["chave"]), "ocorrencias"].sum())
    cobertura = f" {numero(100 * casadas / total, 0)}% das ocorrências do ano citam um bairro da malha." if total else ""
    legenda(lims, cores, f"Ocorrências registradas em {ano}, nos bairros oficiais do IBGE (Censo 2022).{cobertura}",
            casas=0)

    if cd := selecionado(evento, df["cd_bairro"]):
        linha = df.loc[df["cd_bairro"] == cd].iloc[0]
        anos = pd.DataFrame({"ano": ANOS_MAPA}).merge(
            contagens.loc[contagens["chave"] == linha["chave"], ["ano", "ocorrencias"]], on="ano", how="left"
        ).fillna({"ocorrencias": 0})
        painel_bairro(ind, linha["nome"], municipio, anos, ano)
    else:
        st.caption("Clique em um bairro para ver as ocorrências de 2023 a 2025.")


def mapa(con) -> None:
    indicadores, malha, malha_bairros = dados_mapa()
    municipio = st.session_state.get("mapa_municipio")
    st.subheader(f"Bairros de {municipio[1]}" if municipio else "Mapa por município")
    filtros = st.columns([5, 4], vertical_alignment="bottom")
    ind = indicadores[filtros[0].selectbox(
        "Crime", list(indicadores), index=list(indicadores).index("homicidios-e-feminicidios"),
        format_func=lambda i: rotulo_indicador(indicadores[i]), key="mapa_crime")]
    ano = filtros[1].segmented_control("Ano", ANOS_MAPA, default=ANOS_MAPA[-1], required=True, key="mapa_ano")

    if municipio:
        mapa_bairros(con, ind, ano, *municipio, malha_bairros)
    else:
        com_bairros = {f["properties"]["cd_mun"] for f in malha_bairros["features"]}
        mapa_estado(con, ind, ano, malha, com_bairros)


st.set_page_config(page_title="Alerta Capixaba", page_icon=":material/shield:", layout="wide",
                   initial_sidebar_state="auto")
st.markdown(f"<style>{ARQUIVO_CSS.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.session_state.setdefault("historico", [])
st.session_state.setdefault("limite", LimiteSessao(config.MAX_PERGUNTAS_POR_MINUTO))

orquestrador, carregado_em = carregar()
barra_lateral(orquestrador, carregado_em)

with st.container(key="logo-topo"):
    st.image(str(LOGO), width=120)

with st.container(key="painel"):
    coluna_chat, coluna_mapa = st.columns(2, gap="large")

with coluna_mapa:
    mapa(orquestrador.con.cursor())

with coluna_chat.container(key="coluna-chat"):
    if orquestrador.cliente is None:
        st.warning("Chave do Gemini não configurada. Preencha GEMINI_API_KEY em .streamlit/secrets.toml.")

    if not st.session_state.historico:
        boas_vindas()
    for indice, m in enumerate(st.session_state.historico):
        mensagem(m, indice)

    st.caption(AVISO_IA)
    digitada = st.chat_input("Ex.: roubos de celular em Vitória em 2025", key="entrada",
                             max_chars=config.MAX_CARACTERES)
    pergunta = digitada or st.session_state.pop("pendente", None)

    if pergunta:
        st.session_state.historico.append({"papel": "user", "texto": pergunta})
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant"), st.spinner("Consultando dados da SESP-ES…"):
            r = responder(orquestrador, pergunta)
        st.session_state.historico.append({"papel": "assistant", "pergunta": pergunta, "resposta": r})
        st.rerun()
