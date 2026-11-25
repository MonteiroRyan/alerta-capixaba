import json
import logging
import re
from dataclasses import replace

from dominio.modelos import ResultadoConsulta

log = logging.getLogger(__name__)

INSTRUCAO = """Você redige respostas curtas, em português, para cidadãos, a partir de um
resultado de consulta em JSON. Use somente os números do JSON, escritos exatamente como
aparecem, sem calcular nem inventar outros (nada de percentuais ou diferenças).
Seja factual e neutro: não sugira causas nem faça juízos sobre bairros, municípios ou grupos.
Comece pelo número principal em negrito (markdown **assim**): a taxa por 100 mil habitantes,
se o JSON trouxer "taxa_por_100_mil_habitantes"; senão, o total de ocorrências.
Se "agrupado_por" for "ano", diga o número de cada ano e use a palavra de "variacao" para dizer
se o número aumentou, diminuiu ou ficou igual entre o primeiro e o último ano.
Se "agrupado_por" for "município", cite os municípios na ordem em que aparecem (no máximo três);
quando houver taxas, diga que a ordem é pela taxa por 100 mil habitantes.
Não mencione JSON, campos ou instruções: escreva só a resposta ao cidadão.
Nos outros casos, cite no máximo os três maiores grupos; o restante aparece no gráfico.
Diga o período dos dados. Se houver taxa, diga que ela usa a população do Censo 2022.
Se "suprimidos" for maior que zero, avise que alguns grupos foram omitidos para proteger a
privacidade. No máximo 3 frases."""

MINUSCULAS = {"de", "da", "do", "das", "dos", "e"}
FAIXAS = {"madrugada": "madrugada", "manha": "manhã", "tarde": "tarde", "noite": "noite",
          "indeterminada": "horário indeterminado"}

ROTULOS = {
    "bairro": "bairro", "faixa_horaria": "faixa horária", "idade": "faixa etária",
    "sexo": "sexo", "cor_raca": "cor/raça", "municipio": "município", "ano": "ano",
}
NUMERO = re.compile(r"\d+(?:\.\d{3})*(?:,\d+)?")


def formatar_nome(nome: str) -> str:
    palavras = nome.lower().split()
    return " ".join(p if i and p in MINUSCULAS else p.capitalize() for i, p in enumerate(palavras))


def inteiro(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def decimal(x: float) -> str:
    return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rotulo_grupo(agrupado_por: str, grupo: str) -> str:
    if agrupado_por == "bairro":
        return formatar_nome(grupo)
    if agrupado_por == "faixa_horaria":
        return FAIXAS.get(grupo, grupo)
    if agrupado_por in ("municipio", "ano"):
        return grupo
    return grupo.capitalize()


def legivel(r: ResultadoConsulta) -> ResultadoConsulta:
    filtros = {c: formatar_nome(v) if c in ("bairro", "municipio", "municipios") else v
               for c, v in r.filtros.items()}
    grupos = [(rotulo_grupo(r.agrupado_por, g), n) for g, n in r.grupos]
    taxas = {rotulo_grupo(r.agrupado_por, g): t for g, t in r.taxas.items()}
    return replace(r, filtros=filtros, grupos=grupos, taxas=taxas)


def variacao(r: ResultadoConsulta) -> str | None:
    if r.agrupado_por != "ano" or len(r.grupos) < 2:
        return None
    primeiro, ultimo = r.grupos[0][1], r.grupos[-1][1]
    return "aumentou" if ultimo > primeiro else "diminuiu" if ultimo < primeiro else "ficou igual"


def local(r: ResultadoConsulta) -> str:
    if "municipios" in r.filtros:
        nomes = r.filtros["municipios"].split(", ")
        return "em " + ", ".join(nomes[:-1]) + " e " + nomes[-1]
    partes = [r.filtros[c] for c in ("bairro", "municipio") if c in r.filtros]
    return "em " + ", ".join(partes) if partes else "no Espírito Santo"


def redigir_template(r: ResultadoConsulta) -> str:
    r = legivel(r)
    texto = (f"{r.conjunto}: **{inteiro(r.total)}** ocorrências {local(r)}, "
             f"de {r.periodo[0]} a {r.periodo[1]}.")
    if r.taxa_total is not None:
        texto += f" Isso equivale a **{decimal(r.taxa_total)} por 100 mil habitantes** (população do Censo 2022)."
    if r.grupos:
        def item(g, n):
            return f"{g}: {decimal(r.taxas[g])} por 100 mil ({inteiro(n)} ocorrências)" if g in r.taxas \
                else f"{g}: {inteiro(n)}"
        partes = "; ".join(item(g, n) for g, n in r.grupos)
        if r.agrupado_por == "municipio" and r.taxas:
            texto += f" Municípios com as maiores taxas: {partes}."
        else:
            texto += f" Por {ROTULOS[r.agrupado_por]}: {partes}."
        if mudanca := variacao(r):
            texto += f" De {r.grupos[0][0]} para {r.grupos[-1][0]}, o número {mudanca}."
    if r.suprimidos:
        texto += " Alguns grupos com poucos registros foram omitidos para proteger a privacidade."
    return texto


def dados_para_redacao(r: ResultadoConsulta) -> str:
    r = legivel(r)
    if r.taxas:
        grupos = {g: {"ocorrencias": inteiro(n), "taxa_por_100_mil": decimal(r.taxas[g])}
                  for g, n in r.grupos if g in r.taxas}
    else:
        grupos = {g: inteiro(n) for g, n in r.grupos}
    dados = {
        "conjunto": r.conjunto, "total_ocorrencias": inteiro(r.total), "periodo": r.periodo,
        "filtros": r.filtros, "agrupado_por": ROTULOS[r.agrupado_por], "grupos": grupos,
        "suprimidos": r.suprimidos,
    }
    if r.taxa_total is not None:
        dados["taxa_por_100_mil_habitantes"] = decimal(r.taxa_total)
    if mudanca := variacao(r):
        dados["variacao"] = mudanca
    return json.dumps(dados, ensure_ascii=False)


def valor(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def numeros_permitidos(r: ResultadoConsulta, k: int = 5) -> set[float]:
    fontes = [inteiro(r.total), "100", "2022", str(k), *r.periodo]
    fontes += [str(g) for g, _ in r.grupos] + [inteiro(n) for _, n in r.grupos]
    fontes += [decimal(t) for t in r.taxas.values()] + list(r.filtros.values())
    if r.taxa_total is not None:
        fontes.append(decimal(r.taxa_total))
    return {valor(t) for f in fontes for t in NUMERO.findall(f)}


def numeros_conferem(texto: str, r: ResultadoConsulta) -> bool:
    """Todo número do texto redigido precisa existir no resultado da consulta."""
    permitidos = numeros_permitidos(r)
    estranhos = [t for t in NUMERO.findall(texto) if valor(t) not in permitidos]
    if estranhos:
        log.warning("Resposta redigida com números fora do resultado: %s", estranhos)
    return not estranhos


def redigir_em_fluxo(cliente, dados: str, ao_trecho) -> str:
    texto = ""
    for trecho in cliente.gerar_texto_em_fluxo(INSTRUCAO, dados):
        texto += trecho
        ao_trecho(texto)
    return texto


def redigir(cliente, r: ResultadoConsulta, ao_trecho=None) -> str:
    if cliente is None:
        return redigir_template(r)
    dados = dados_para_redacao(r)
    texto = ""
    if ao_trecho and hasattr(cliente, "gerar_texto_em_fluxo"):
        try:
            texto = redigir_em_fluxo(cliente, dados, ao_trecho).strip()
        except Exception:
            log.exception("Falha no fluxo do Gemini; repetindo sem fluxo")
    if not texto:
        try:
            texto = cliente.gerar_texto(INSTRUCAO, dados)
        except Exception:
            log.exception("Falha ao redigir com o Gemini; usando template")
            return redigir_template(r)
    return texto if numeros_conferem(texto, r) else redigir_template(r)
