import duckdb

from dados.registry import ConjuntoDados
from dominio.modelos import Intencao, ResultadoConsulta

FAIXA_ETARIA = """CASE
    WHEN idade IS NULL THEN NULL
    WHEN idade < 12 THEN '0 a 11'
    WHEN idade < 18 THEN '12 a 17'
    WHEN idade < 25 THEN '18 a 24'
    WHEN idade < 35 THEN '25 a 34'
    WHEN idade < 45 THEN '35 a 44'
    WHEN idade < 60 THEN '45 a 59'
    ELSE '60 ou mais' END"""

AGRUPAMENTOS = {
    "idade": FAIXA_ETARIA,
    "sexo": "sexo",
    "cor_raca": "cor_raca",
    "faixa_horaria": "faixa_horaria",
    "bairro": "bairro",
}
MAX_GRUPOS = 10


def escolher_agrupamento(intencao: Intencao) -> str:
    if intencao.perfil:
        return intencao.perfil
    if intencao.agrupar_por:
        return intencao.agrupar_por
    if intencao.bairro:
        return "faixa_horaria"
    return "bairro"


def consultar(con: duckdb.DuckDBPyConnection, conjunto: ConjuntoDados, intencao: Intencao) -> ResultadoConsulta:
    filtros = {c: getattr(intencao, c) for c in ("municipio", "bairro", "faixa_horaria") if getattr(intencao, c)}
    condicoes = [f"{c} = ?" for c in filtros]
    params = list(filtros.values())
    if intencao.ano:
        condicoes.append("year(data_fato) = ?")
        params.append(intencao.ano)
        filtros["ano"] = str(intencao.ano)
    where = " AND ".join(condicoes) or "TRUE"
    tabela = f'"{conjunto.id}"'

    total, inicio, fim = con.execute(
        f"SELECT COUNT(DISTINCT ocorrencia), MIN(data_fato), MAX(data_fato) FROM {tabela} WHERE {where}", params
    ).fetchone()

    agrupado_por = escolher_agrupamento(intencao)
    contagem = "COUNT(*)" if intencao.perfil else "COUNT(DISTINCT ocorrencia)"
    linhas = con.execute(
        f"SELECT COALESCE({AGRUPAMENTOS[agrupado_por]}, 'não informado') AS g, {contagem} AS n "
        f"FROM {tabela} WHERE {where} GROUP BY g ORDER BY n DESC LIMIT {MAX_GRUPOS}",
        params,
    ).fetchall()

    return ResultadoConsulta(
        conjunto=conjunto.nome,
        total=total,
        agrupado_por=agrupado_por,
        grupos=[(str(g), int(n)) for g, n in linhas],
        periodo=(inicio.strftime("%d/%m/%Y") if inicio else "", fim.strftime("%d/%m/%Y") if fim else ""),
        filtros=filtros,
    )
