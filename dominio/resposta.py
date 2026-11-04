"""GeradorResposta: redige a resposta com prompt estrito e fallback por template (AD07)."""
import json
import logging
from dataclasses import replace

from dominio.modelos import ResultadoConsulta

log = logging.getLogger(__name__)

INSTRUCAO = """Você redige respostas curtas, em português, para cidadãos, a partir de um
resultado de consulta em JSON. Use somente os números do JSON, sem calcular nem inventar
outros. Seja factual e neutro: não sugira causas nem faça juízos sobre bairros ou grupos.
Comece pelo número total em negrito (markdown **assim**), com separador de milhar.
Diga o período dos dados e cite no máximo os três maiores grupos; o restante aparece no gráfico.
Se "suprimidos" for maior que zero, avise que alguns grupos foram omitidos para proteger a
privacidade. No máximo 3 frases."""

MINUSCULAS = {"de", "da", "do", "das", "dos", "e"}
FAIXAS = {"madrugada": "madrugada", "manha": "manhã", "tarde": "tarde", "noite": "noite",
          "indeterminada": "horário indeterminado"}

ROTULOS = {
    "bairro": "bairro", "faixa_horaria": "faixa horária", "idade": "faixa etária",
    "sexo": "sexo", "cor_raca": "cor/raça",
}


def formatar_nome(nome: str) -> str:
    """'PRAIA DA COSTA' -> 'Praia da Costa'."""
    palavras = nome.lower().split()
    return " ".join(p if i and p in MINUSCULAS else p.capitalize() for i, p in enumerate(palavras))


def rotulo_grupo(agrupado_por: str, grupo: str) -> str:
    if agrupado_por == "bairro":
        return formatar_nome(grupo)
    if agrupado_por == "faixa_horaria":
        return FAIXAS.get(grupo, grupo)
    return grupo.capitalize()


def legivel(r: ResultadoConsulta) -> ResultadoConsulta:
    """Cópia do resultado com nomes de lugares e grupos prontos para exibição."""
    filtros = {c: formatar_nome(v) if c in ("bairro", "municipio") else v for c, v in r.filtros.items()}
    grupos = [(rotulo_grupo(r.agrupado_por, g), n) for g, n in r.grupos]
    return replace(r, filtros=filtros, grupos=grupos)


def redigir_template(r: ResultadoConsulta) -> str:
    r = legivel(r)
    local = ", ".join(r.filtros[c] for c in ("bairro", "municipio") if c in r.filtros) or "Espírito Santo"
    texto = f"{r.conjunto}: {r.total} ocorrências em {local}, de {r.periodo[0]} a {r.periodo[1]}."
    if r.grupos:
        partes = "; ".join(f"{g}: {n}" for g, n in r.grupos)
        texto += f" Por {ROTULOS[r.agrupado_por]}: {partes}."
    if r.suprimidos:
        texto += " Alguns grupos com poucos registros foram omitidos para proteger a privacidade."
    return texto


def redigir(cliente, r: ResultadoConsulta) -> str:
    if cliente is None:
        return redigir_template(r)
    r = legivel(r)
    dados = {
        "conjunto": r.conjunto, "total_ocorrencias": r.total, "periodo": r.periodo,
        "filtros": r.filtros, "agrupado_por": ROTULOS[r.agrupado_por],
        "grupos": dict(r.grupos), "suprimidos": r.suprimidos,
    }
    try:
        return cliente.gerar_texto(INSTRUCAO, json.dumps(dados, ensure_ascii=False))
    except Exception:
        log.exception("Falha ao redigir com o Gemini; usando template")
        return redigir_template(r)
