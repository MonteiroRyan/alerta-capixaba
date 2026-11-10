from datetime import datetime

import streamlit as st

from dominio.orquestrador import Orquestrador
from infra import config
from ui.chat import nova_conversa

PORTAL = "https://dados.es.gov.br/organization/sesp"
ARQUIVO_CSS = config.RAIZ / "styles.css"
LOGO = config.RAIZ / "static" / "logo-alerta-capixaba.png"
LOGO_URL = "app/static/logo-alerta-capixaba.png"
SUBTITULO = "Dados de segurança pública do Espírito Santo"


@st.cache_resource
def folha_de_estilo() -> str:
    return f"<style>{ARQUIVO_CSS.read_text(encoding='utf-8')}</style>"


def aplicar_estilo() -> None:
    st.html(folha_de_estilo())


def cabecalho(cobertura: dict) -> None:
    inicio, fim = cobertura["anos"]
    st.html(
        '<header class="marca">'
        f'<img src="{LOGO_URL}" alt="Alerta Capixaba" width="74" height="72">'
        f'<p><span class="lema">{SUBTITULO}</span>'
        f'<span class="origem">Fonte: SESP-ES · dados de {inicio} a {fim}</span></p>'
        "</header>"
    )


def barra_lateral(orquestrador: Orquestrador, cobertura: dict, carregado_em: datetime) -> None:
    with st.sidebar:
        st.image(str(LOGO), width=168)
        st.caption(SUBTITULO)
        st.button("Nova conversa", icon=":material/add:", on_click=nova_conversa, width="stretch")

        perguntas = [m["texto"] for m in st.session_state.historico if m["papel"] == "user"]
        if perguntas:
            st.subheader("Nesta conversa", anchor=False)
            for p in reversed(perguntas[-8:]):
                st.markdown(f"- {p}")

        st.subheader("Sobre os dados", anchor=False)
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

        st.subheader("Aviso", anchor=False)
        st.markdown("Este site não registra ocorrências. Em emergência, ligue **190**.")
