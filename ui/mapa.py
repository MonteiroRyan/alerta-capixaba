import html
import logging
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dados.registry import IndicadorMapa
from dados.repositorio import chave
from dominio.mapa import bairros_do_municipio, classificar, historico, limites, ocorrencias_bairros, taxas

log = logging.getLogger(__name__)

ANOS = [2023, 2024, 2025]
ALTURA = 420
RAMPA = ["#FBEAF1", "#F4BFD5", "#E48AAE", "#C1457E", "#8E1450"]
COR_DIVISA = "#7C6B76"
COR_SELECAO = "#005A8C"
FONTE = '"Source Sans", "Source Sans Pro", sans-serif'
CONFIG = {
    "scrollZoom": True, "displayModeBar": True, "displaylogo": False, "doubleClick": "reset",
    "topojsonURL": "app/static/",
    "modeBarButtons": [["zoomInGeo", "zoomOutGeo", "resetGeo"]],
}
INDICADOR_PADRAO = "homicidios-e-feminicidios"
MOSTRAR_PAINEL = """<script>
(() => {
  const painel = document.querySelector('.st-key-detalhe-mapa');
  if (!painel) return;
  const suave = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const coluna = painel.closest('[data-testid="stColumn"]');
  requestAnimationFrame(() => {
    if (coluna && coluna.scrollHeight > coluna.clientHeight + 1) {
      coluna.scrollTo({ top: coluna.scrollHeight, behavior: suave ? 'smooth' : 'auto' });
    } else {
      painel.scrollIntoView({ behavior: suave ? 'smooth' : 'auto', block: 'nearest' });
    }
  });
})();
</script>"""


def numero(valor: float, casas: int = 1) -> str:
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def rotulo_indicador(ind: IndicadorMapa) -> str:
    return ind.nome if ind.nome == ind.grupo else f"{ind.grupo} › {ind.nome}"


def cores_das_classes(k: int) -> list[str]:
    return [RAMPA[round(i * (len(RAMPA) - 1) / (k - 1))] for i in range(k)] if k > 1 else RAMPA[:1]


def rotulos_das_classes(lims: list[float], casas: int) -> list[str]:
    rotulos, anterior = [], None
    for lim in lims:
        if lim == 0:
            rotulos.append("Sem registro")
        elif casas == 0:
            menor = int(anterior or 0) + 1
            rotulos.append(str(menor) if menor >= lim else f"{numero(menor, 0)} a {numero(lim, 0)}")
        elif not anterior:
            rotulos.append(f"até {numero(lim, casas)}")
        else:
            rotulos.append(f"{numero(anterior, casas)} a {numero(lim, casas)}")
        anterior = lim
    return rotulos


def selecao_atual() -> str | None:
    try:
        pontos = st.session_state["mapa"]["selection"]["points"]
    except (KeyError, TypeError):
        pontos = []
    if pontos and (local := pontos[0].get("location")):
        st.session_state.mapa_selecao = local
    return st.session_state.get("mapa_selecao")


def limpar_selecao() -> None:
    st.session_state.mapa_selecao = None
    st.session_state.pop("mapa", None)


def figura(malha: dict, idkey: str, ids: pd.Series, classes, cores: list[str], nomes: pd.Series,
           valores: pd.Series, unidade: str, revisao: str, selecionado: str | None) -> go.Figure:
    k = len(cores)
    degraus = [[pos, c] for i, c in enumerate(cores) for pos in (i / k, (i + 1) / k)]
    comum = dict(featureidkey=f"properties.{idkey}", zmin=0, zmax=k, colorscale=degraus, showscale=False)
    fig = go.Figure(go.Choropleth(
        geojson=malha, locations=ids, z=classes + 0.5, marker_line=dict(color=COR_DIVISA, width=0.6),
        customdata=list(zip(nomes, valores)),
        hovertemplate=f"<b>%{{customdata[0]}}</b><br>%{{customdata[1]}} {unidade}<extra></extra>",
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)), **comum,
    ))
    destaque = [f for f in malha["features"] if f["properties"][idkey] == selecionado]
    if destaque and (ids == selecionado).any():
        fig.add_trace(go.Choropleth(
            geojson={"type": "FeatureCollection", "features": destaque}, locations=[selecionado],
            z=[classes[(ids == selecionado).to_numpy().argmax()] + 0.5],
            marker_line=dict(color=COR_SELECAO, width=2.5), hoverinfo="skip", **comum,
        ))
    fig.update_geos(fitbounds="locations", projection_type="mercator", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=ALTURA, dragmode="pan", uirevision=revisao,
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="rgba(27,36,48,0.18)",
                        font=dict(family=FONTE, size=14, color="#1B2430")),
    )
    return fig


def legenda(descricao: str, titulo: str, lims: list[float], cores: list[str], nota: str, casas: int = 1) -> None:
    itens = "".join(
        f'<li><span class="amostra" style="background:{cor}"></span>{html.escape(rotulo)}</li>'
        for cor, rotulo in zip(cores, rotulos_das_classes(lims, casas))
    )
    st.html(f'<div class="legenda-mapa"><p class="so-leitor">{html.escape(descricao)}</p>'
            f'<p class="legenda-titulo">{html.escape(titulo)}</p>'
            f'<ul aria-label="Legenda do mapa">{itens}</ul><p class="legenda-nota">{html.escape(nota)}</p></div>')


def serie_anual(linhas: list[tuple[int, str, str | None]], ano: int) -> str:
    blocos = "".join(
        f'<div class="ano{" atual" if a == ano else ""}"><span class="rotulo">{a}</span>'
        f'<span class="valor">{html.escape(valor)}</span>'
        + (f'<span class="detalhe">{html.escape(detalhe)}</span>' if detalhe else "") + "</div>"
        for a, valor, detalhe in linhas
    )
    return f'<div class="serie-anual">{blocos}</div>'


def cabecalho_painel(nome: str, detalhe: str) -> str:
    return (f'<div class="painel-titulo"><p class="nome">{html.escape(nome)}</p>'
            f'<p class="detalhe">{html.escape(detalhe)}</p></div>')


def levar_ao_chat(pergunta: str) -> None:
    st.session_state.rascunho = pergunta
    st.rerun()


def ver_bairros(codigo: str, nome: str) -> None:
    st.session_state.mapa_municipio = (codigo, nome)
    limpar_selecao()


def voltar_ao_estado() -> None:
    st.session_state.mapa_municipio = None
    limpar_selecao()


def topo_do_painel(nome: str, detalhe: str, linhas: list, ano: int) -> None:
    st.button("", icon=":material/close:", type="tertiary", help="Fechar", key="fechar_detalhe",
              on_click=limpar_selecao)
    st.html(cabecalho_painel(nome, detalhe) + serie_anual(linhas, ano))
    if st.session_state.get("mapa_painel_visto") != nome:
        st.session_state.mapa_painel_visto = nome
        st.html(MOSTRAR_PAINEL, unsafe_allow_javascript=True)


def painel_municipio(con, ind: IndicadorMapa, codigo: str, nome: str, ano: int, tem_bairros: bool) -> None:
    df = historico(con, ind.id, codigo, ANOS)
    linhas = [(int(a), numero(t), f"{numero(n, 0)} ocorrências") for a, t, n in
              zip(df["ano"], df["taxa"], df["ocorrencias"])]
    with st.container(key="detalhe-mapa"):
        topo_do_painel(nome, f"{ind.nome} · ocorrências por 100 mil habitantes", linhas, ano)
        with st.container(horizontal=True):
            if st.button("Perguntar sobre este município", icon=":material/chat:", key="perguntar_municipio"):
                levar_ao_chat(f"Quantos casos de {ind.nome.lower()} houve em {nome} em {ano}?")
            if tem_bairros:
                st.button("Ver bairros", icon=":material/map:", on_click=ver_bairros, args=(codigo, nome))
        if not tem_bairros:
            st.caption("O IBGE não publica a divisão oficial de bairros deste município.")


def painel_bairro(ind: IndicadorMapa, nome: str, municipio: str, anos: pd.DataFrame, ano: int) -> None:
    linhas = [(int(a), numero(n, 0), None) for a, n in zip(anos["ano"], anos["ocorrencias"])]
    with st.container(key="detalhe-mapa"):
        topo_do_painel(nome, f"{ind.nome} · ocorrências em {municipio}", linhas, ano)
        if st.button("Perguntar sobre este bairro", icon=":material/chat:", key="perguntar_bairro"):
            levar_ao_chat(f"Quantos casos de {ind.nome.lower()} houve no bairro {nome} em {municipio} em {ano}?")


def desenhar(fig: go.Figure) -> None:
    with st.container(key="caixa-mapa"):
        st.plotly_chart(fig, key="mapa", on_select="rerun", selection_mode="points", config=CONFIG)


def mapa_estado(con, ind: IndicadorMapa, ano: int, malha: dict, com_bairros: set[str]) -> None:
    df = taxas(con, ind.id, ano)
    lims = limites(df["taxa"])
    cores = cores_das_classes(len(lims))
    codigo = selecao_atual()
    fig = figura(malha, "codarea", df["codigo_ibge"], classificar(df["taxa"], lims), cores,
                 df["municipio"], df["taxa"].map(numero), "por 100 mil hab.", "estado", codigo)
    desenhar(fig)
    if not df["ocorrencias"].any():
        st.info(f"Nenhuma ocorrência de {ind.nome.lower()} foi registrada em {ano}.", icon=":material/info:")
    legenda(f"Mapa do Espírito Santo com os municípios coloridos pela taxa de {ind.nome.lower()} em {ano}.",
            f"Ocorrências por 100 mil habitantes em {ano}", lims, cores,
            "Fonte: SESP-ES. População do Censo 2022 (IBGE).")

    if codigo and (df["codigo_ibge"] == codigo).any():
        nome = df.loc[df["codigo_ibge"] == codigo, "municipio"].iloc[0]
        painel_municipio(con, ind, codigo, nome, ano, codigo in com_bairros)
    else:
        st.session_state.mapa_painel_visto = None
        st.caption("Toque em um município para ver os números de 2023 a 2025 e, quando houver, o mapa por bairro.")


def mapa_bairros(con, ind: IndicadorMapa, ano: int, codigo: str, municipio: str, malha_bairros: dict) -> None:
    recorte = bairros_do_municipio(malha_bairros, codigo)
    df = pd.DataFrame([f["properties"] for f in recorte["features"]])
    df["chave"] = df["nome"].map(chave)
    contagens = ocorrencias_bairros(con, ind.id, chave(municipio), ANOS)
    no_ano = contagens[contagens["ano"] == ano]
    df = df.merge(no_ano[["chave", "ocorrencias"]], on="chave", how="left").fillna({"ocorrencias": 0})

    lims = sorted({float(math.floor(l)) for l in limites(df["ocorrencias"])})
    cores = cores_das_classes(len(lims))
    cd = selecao_atual()
    fig = figura(recorte, "cd_bairro", df["cd_bairro"], classificar(df["ocorrencias"], lims), cores,
                 df["nome"], df["ocorrencias"].map(lambda n: numero(n, 0)), "ocorrências", f"bairros-{codigo}", cd)
    desenhar(fig)

    total = int(no_ano["ocorrencias"].sum())
    casadas = int(no_ano.loc[no_ano["chave"].isin(df["chave"]), "ocorrencias"].sum())
    if not total:
        st.info(f"Nenhuma ocorrência de {ind.nome.lower()} foi registrada em {municipio} em {ano}.",
                icon=":material/info:")
    cobertura = (f" {numero(100 * casadas / total, 0)}% das ocorrências do ano informam um bairro que está no mapa."
                 if total else "")
    legenda(f"Mapa de {municipio} com os bairros coloridos pelo número de ocorrências de {ind.nome.lower()} em {ano}.",
            f"Ocorrências registradas em {ano}", lims, cores,
            f"Fonte: SESP-ES. Bairros oficiais do IBGE (Censo 2022).{cobertura}", casas=0)

    if cd and (df["cd_bairro"] == cd).any():
        linha = df.loc[df["cd_bairro"] == cd].iloc[0]
        anos = pd.DataFrame({"ano": ANOS}).merge(
            contagens.loc[contagens["chave"] == linha["chave"], ["ano", "ocorrencias"]], on="ano", how="left"
        ).fillna({"ocorrencias": 0})
        painel_bairro(ind, linha["nome"], municipio, anos, ano)
    else:
        st.session_state.mapa_painel_visto = None
        st.caption("Toque em um bairro para ver os números de 2023 a 2025.")


@st.fragment
def mapa(con, indicadores: dict[str, IndicadorMapa], malha: dict, malha_bairros: dict) -> None:
    municipio = st.session_state.get("mapa_municipio")
    with st.container(key="painel-mapa"):
        if municipio:
            st.button("Voltar ao mapa do estado", icon=":material/arrow_back:", on_click=voltar_ao_estado,
                      type="tertiary")
        st.subheader(f"Bairros de {municipio[1]}" if municipio else "Mapa por município", anchor="mapa")
        with st.container(key="filtros-mapa", horizontal=True, vertical_alignment="bottom"):
            ind = indicadores[st.selectbox(
                "Tipo de crime", list(indicadores), index=list(indicadores).index(INDICADOR_PADRAO),
                format_func=lambda i: rotulo_indicador(indicadores[i]), key="mapa_crime")]
            ano = st.segmented_control("Ano", ANOS, default=ANOS[-1], required=True, key="mapa_ano",
                                       width="content")
        try:
            if municipio:
                mapa_bairros(con, ind, ano, *municipio, malha_bairros)
            else:
                com_bairros = {f["properties"]["cd_mun"] for f in malha_bairros["features"]}
                mapa_estado(con, ind, ano, malha, com_bairros)
        except Exception:
            log.exception("Falha ao montar o mapa")
            st.warning("Não foi possível mostrar o mapa agora. As perguntas ao lado continuam funcionando.",
                       icon=":material/map:")
