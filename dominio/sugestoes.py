from dados.registry import ConjuntoDados
from dominio.modelos import Intencao
from dominio.resposta import formatar_nome

EXEMPLOS = [
    ("Quantos roubos de celular houve em Vila Velha em 2025?", "Número em um período"),
    ("Em quais bairros de Serra houve mais casos de violência doméstica?", "Ranking"),
    ("Qual a cor/raça das vítimas de homicídio no ES em 2024?", "Perfil das vítimas"),
    ("Em que horário acontecem mais roubos de celular em Vitória?", "Horário"),
]

FORA_DO_ESCOPO = [
    "Roubos de celular em Vitória em 2025",
    "Homicídios em Cariacica por faixa horária",
]

PERFIS = {"idade": "faixa etária", "sexo": "sexo", "cor_raca": "cor/raça"}
FAIXAS = {"madrugada": "de madrugada", "manha": "de manhã", "tarde": "à tarde", "noite": "à noite"}


def descrever(nome: str, intencao: Intencao) -> str:
    texto = f"Taxa de {nome.lower()} por 100 mil habitantes" if intencao.medida == "taxa" else nome
    if intencao.bairro:
        texto += f" no bairro {formatar_nome(intencao.bairro)}"
    if intencao.municipio:
        texto += f" em {formatar_nome(intencao.municipio)}"
    if intencao.municipios:
        nomes = [formatar_nome(m) for m in intencao.municipios]
        texto += " em " + ", ".join(nomes[:-1]) + " e " + nomes[-1]
    if not intencao.bairro and not intencao.municipio and not intencao.municipios:
        texto += " no ES"
    if intencao.ano:
        texto += f" em {intencao.ano}"
    if intencao.anos:
        texto += f" de {intencao.anos[0]} a {intencao.anos[-1]}"
    if intencao.agrupar_por == "municipio" and not intencao.municipios:
        texto += ", por município"
    if intencao.faixa_horaria:
        texto += f" {FAIXAS[intencao.faixa_horaria]}"
    if intencao.perfil:
        texto += f", por {PERFIS[intencao.perfil]} das vítimas"
    return texto


def continuacoes(conjunto: ConjuntoDados, intencao: Intencao, conjuntos: dict[str, ConjuntoDados],
                 anos: list[int]) -> list[str]:
    opcoes = []
    if conjunto.tem_perfil and not intencao.perfil:
        opcoes.append(descrever(conjunto.nome, intencao.model_copy(
            update={"perfil": "sexo", "medida": "contagem", "agrupar_por": None, "municipios": [], "anos": []})))
    if intencao.anos:
        ano = None
    elif intencao.ano:
        ano = intencao.ano - 1 if intencao.ano - 1 in anos else None
    else:
        ano = anos[-1]
    if ano:
        opcoes.append(descrever(conjunto.nome, intencao.model_copy(update={"ano": ano, "anos": []})))
    outro = next(c for c in conjuntos.values() if c.id != conjunto.id)
    opcoes.append(descrever(outro.nome, intencao.model_copy(update={"perfil": None})))
    return opcoes[:3]


def candidatos(pergunta: str, conjuntos: dict[str, ConjuntoDados]) -> list[ConjuntoDados]:
    texto = pergunta.lower()
    prefixos = [p for p, palavras in (("roubo", ("roub", "assalt")), ("furto", ("furt",)))
                if any(w in texto for w in palavras)]
    escolhidos = [c for c in conjuntos.values() if any(c.id.startswith(p) for p in prefixos)]
    return escolhidos or list(conjuntos.values())


def para_recorte(motivo: str, intencao: Intencao, pergunta: str, conjuntos: dict[str, ConjuntoDados],
                 anos: list[int] | None) -> list[str]:
    nome = conjuntos[intencao.tipo_crime].nome if intencao.tipo_crime in conjuntos else ""
    if motivo == "tipo":
        return [descrever(c.nome, intencao) for c in candidatos(pergunta, conjuntos)]
    if motivo == "perfil":
        return [descrever(nome, intencao.model_copy(update={"perfil": None}))]
    if motivo in ("bairro", "municipio"):
        return [descrever(nome, intencao.model_copy(update={"bairro": None, "municipio": None}))]
    if motivo == "taxa":
        return [descrever(nome, intencao.model_copy(update={"medida": "contagem"}))]
    if motivo == "ano" and anos:
        return [descrever(nome, intencao.model_copy(update={"ano": anos[-1]}))]
    return []
