import altair as alt
import pandas as pd
import streamlit as st

from dominio.orquestrador import Orquestrador, Resposta
from dominio.resposta import ROTULOS, formatar_nome, legivel
from dominio.sugestoes import EXEMPLOS, FAIXAS, PERFIS
from infra import avaliacoes, config

AVISO_IA = "As respostas são geradas por IA e podem conter erros. Confira a fonte indicada em cada resposta."
EXEMPLO_ENTRADA = "Ex.: roubos de celular em Vitória em 2025"
AVATAR_CIDADAO = ":material/person:"
AVATAR_ASSISTENTE = ":material/shield:"
PENSANDO = ('<div class="pensando" role="status"><span class="pontos" aria-hidden="true"><i></i><i></i><i></i></span>'
            "Consultando os dados da SESP-ES…</div>")
ROLAR = """<script>
(() => {
  const alvos = document.querySelectorAll('[class*="st-key-pergunta-"]');
  const alvo = alvos[alvos.length - 1];
  if (!alvo) return;
  const suave = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  requestAnimationFrame(() => alvo.scrollIntoView({ behavior: suave ? 'smooth' : 'auto', block: 'start' }));
})();
</script>"""


def perguntar(texto: str) -> None:
    st.session_state.pendente = texto


def nova_conversa() -> None:
    st.session_state.historico = []


def ao_escolher(chave: str) -> None:
    if escolha := st.session_state.get(chave):
        perguntar(escolha)


def ao_avaliar(chave: str, pergunta: str, resposta: str) -> None:
    valor = st.session_state.get(chave)
    if valor is not None:
        avaliacoes.registrar(config.ARQUIVO_AVALIACOES, pergunta, resposta, util=valor == 1)


def boas_vindas() -> None:
    with st.container(key="boas-vindas"):
        st.title("Pergunte sobre a segurança pública no Espírito Santo", anchor=False)
        st.markdown("As respostas usam os dados abertos da Secretaria de Segurança Pública (SESP-ES). "
                    "Escreva do jeito que você falaria.")
        st.caption("Experimente perguntar")
        colunas = st.columns(2)
        for i, (pergunta, tipo) in enumerate(EXEMPLOS):
            with colunas[i % 2]:
                st.button(f":gray[{tipo}]  \n{pergunta}", key=f"exemplo{i}", on_click=perguntar,
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
    return alt.Chart(df).mark_bar(color=config.COR_PRIMARIA, cornerRadiusEnd=4).encode(
        x=alt.X("Ocorrências:Q", title="Ocorrências", axis=alt.Axis(format="d")),
        y=alt.Y(f"{rotulo}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        tooltip=[rotulo, "Ocorrências"],
    ).properties(height=28 * len(df) + 40, background="transparent")


def resposta_com_dados(r: Resposta, indice: int, pergunta: str) -> None:
    st.markdown(r.texto)
    resultado = legivel(r.resultado)
    df = None
    if resultado.grupos:
        rotulo = ROTULOS[resultado.agrupado_por].capitalize()
        df = pd.DataFrame(resultado.grupos, columns=[rotulo, "Ocorrências"])
        st.altair_chart(grafico(df, rotulo))

    inicio, fim = resultado.periodo
    st.caption(f"Fonte: SESP-ES, dados abertos · {r.conjunto.nome} · de {inicio} a {fim} · "
               f"[abrir o conjunto de dados]({r.conjunto.url})")
    como_entendi(r)

    with st.container(key=f"acoes-{indice}", horizontal=True, vertical_alignment="center"):
        if df is not None:
            with st.popover("Ver tabela"):
                st.dataframe(df, hide_index=True)
            st.download_button("Baixar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="alerta-capixaba.csv", mime="text/csv", key=f"csv{indice}",
                               icon=":material/download:")
        with st.container(key=f"avaliar-{indice}", horizontal=True, vertical_alignment="center",
                          horizontal_alignment="right"):
            st.caption("A resposta foi útil?")
            chave = f"avaliacao{indice}"
            st.feedback("thumbs", key=chave, on_change=ao_avaliar, args=(chave, pergunta, r.texto))


def sugestoes(r: Resposta, indice: int) -> None:
    if r.opcoes:
        chave = f"sugestao{indice}"
        st.pills("Você também pode perguntar", r.opcoes, key=chave, on_change=ao_escolher, args=(chave,),
                 label_visibility="visible" if r.tipo == "resposta" else "collapsed")


def mensagem_cidadao(texto: str, indice: int) -> None:
    with st.container(key=f"pergunta-{indice}"), st.chat_message("user", avatar=AVATAR_CIDADAO):
        st.markdown(texto)


def mensagem(m: dict, indice: int) -> None:
    if m["papel"] == "user":
        mensagem_cidadao(m["texto"], indice)
        return
    r: Resposta = m["resposta"]
    with st.container(key=f"resposta-{indice}"), st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        if r.tipo == "resposta":
            resposta_com_dados(r, indice, m["pergunta"])
        elif r.tipo == "erro":
            st.error(r.texto, icon=":material/error:")
            st.button("Tentar novamente", type="primary", key=f"repetir{indice}", icon=":material/refresh:",
                      on_click=perguntar, args=(m["pergunta"],))
        else:
            st.markdown(r.texto)
        sugestoes(r, indice)


def responder(orquestrador: Orquestrador, teto, pergunta: str, ao_trecho) -> Resposta:
    if not st.session_state.limite.permitir():
        return Resposta("Você fez muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo.", "aviso")
    if not teto.permitir():
        return Resposta("O limite diário de perguntas foi atingido. Tente de novo amanhã.", "aviso")
    return orquestrador.responder(pergunta, ao_trecho)


def conversa(orquestrador: Orquestrador, teto) -> None:
    historico = st.session_state.historico
    if orquestrador.cliente is None:
        st.warning("O assistente de perguntas está indisponível no momento. O mapa continua funcionando.",
                   icon=":material/info:")
    if not historico:
        boas_vindas()
    for indice, m in enumerate(historico):
        mensagem(m, indice)

    if "rascunho" in st.session_state:
        st.session_state.entrada = st.session_state.pop("rascunho")
    area_pendente = st.container(key="pendente")
    with st.container(key="compositor"):
        digitada = st.chat_input(EXEMPLO_ENTRADA, key="entrada", max_chars=config.MAX_CARACTERES)
    with st.container(key="aviso-ia"):
        st.caption(AVISO_IA)
        st.html('<a class="atalho-mapa" href="#mapa">Ver o mapa por município ↓</a>')
    pergunta = digitada or st.session_state.pop("pendente", None)

    if pergunta:
        historico.append({"papel": "user", "texto": pergunta})
        with area_pendente:
            mensagem_cidadao(pergunta, len(historico) - 1)
            with st.container(key="resposta-pendente"), st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
                area = st.empty()
                area.html(PENSANDO)
                st.html(ROLAR, unsafe_allow_javascript=True)
                r = responder(orquestrador, teto, pergunta, area.markdown)
        historico.append({"papel": "assistant", "pergunta": pergunta, "resposta": r})
        st.session_state.rolar = True
        st.rerun()
    elif st.session_state.pop("rolar", False):
        st.html(ROLAR, unsafe_allow_javascript=True)
