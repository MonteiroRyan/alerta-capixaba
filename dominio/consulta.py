import duckdb

from dados.registry import ConjuntoDados
from dominio.modelos import Intencao, ResultadoConsulta

FAIXA_ETARIA = """CASE
    WHEN t.idade IS NULL THEN NULL
    WHEN t.idade < 12 THEN '0 a 11'
    WHEN t.idade < 18 THEN '12 a 17'
    WHEN t.idade < 25 THEN '18 a 24'
    WHEN t.idade < 35 THEN '25 a 34'
    WHEN t.idade < 45 THEN '35 a 44'
    WHEN t.idade < 60 THEN '45 a 59'
    ELSE '60 ou mais' END"""

AGRUPAMENTOS = {
    "idade": FAIXA_ETARIA,
    "sexo": "t.sexo",
    "cor_raca": "t.cor_raca",
    "faixa_horaria": "t.faixa_horaria",
    "bairro": "t.bairro",
    "municipio": "COALESCE(p.municipio, t.municipio)",
    "ano": "CAST(year(t.data_fato) AS VARCHAR)",
}
MAX_GRUPOS = 10
POR_HABITANTES = 100_000
CHAVE_SQL = r"regexp_replace(trim(upper(strip_accents({}))), '\s+', ' ', 'g')"
JUNCAO_POPULACAO = f"LEFT JOIN populacao p ON {CHAVE_SQL.format('t.municipio')} = {CHAVE_SQL.format('p.municipio')}"


class SemPopulacao(Exception):
    pass


def escolher_agrupamento(intencao: Intencao) -> str:
    if intencao.perfil:
        return intencao.perfil
    if intencao.agrupar_por:
        return intencao.agrupar_por
    if intencao.bairro:
        return "faixa_horaria"
    if intencao.medida == "taxa" and not intencao.municipio:
        return "municipio"
    return "bairro"


def tem_populacao(con: duckdb.DuckDBPyConnection) -> bool:
    return bool(con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'populacao'").fetchone()[0])


def populacao(con: duckdb.DuckDBPyConnection, municipios: list[str]) -> int | None:
    if not municipios:
        return con.execute("SELECT SUM(populacao) FROM populacao").fetchone()[0]
    marcas = ", ".join("?" for _ in municipios)
    pop, casados = con.execute(
        f"SELECT SUM(populacao), COUNT(*) FROM populacao WHERE {CHAVE_SQL.format('municipio')} IN "
        f"(SELECT {CHAVE_SQL.format('m')} FROM (SELECT unnest([{marcas}]) AS m))", municipios).fetchone()
    return pop if casados == len(municipios) else None


def taxa(n: int, pop: int | None) -> float | None:
    return n * POR_HABITANTES / pop if pop else None


def consultar(con: duckdb.DuckDBPyConnection, conjunto: ConjuntoDados, intencao: Intencao) -> ResultadoConsulta:
    filtros = {c: getattr(intencao, c) for c in ("municipio", "bairro", "faixa_horaria") if getattr(intencao, c)}
    condicoes = [f"t.{c} = ?" for c in filtros]
    params: list = list(filtros.values())
    if intencao.municipios:
        condicoes.append(f"t.municipio IN ({', '.join('?' for _ in intencao.municipios)})")
        params += intencao.municipios
        filtros["municipios"] = ", ".join(intencao.municipios)
    if intencao.anos:
        condicoes.append(f"year(t.data_fato) IN ({', '.join('?' for _ in intencao.anos)})")
        params += intencao.anos
        filtros["anos"] = ", ".join(map(str, intencao.anos))
    elif intencao.ano:
        condicoes.append("year(t.data_fato) = ?")
        params.append(intencao.ano)
        filtros["ano"] = str(intencao.ano)
    where = " AND ".join(condicoes) or "TRUE"
    tabela = f'"{conjunto.id}" t'

    total, inicio, fim = con.execute(
        f"SELECT COUNT(DISTINCT t.ocorrencia), MIN(t.data_fato), MAX(t.data_fato) FROM {tabela} WHERE {where}",
        params,
    ).fetchone()

    agrupado_por = escolher_agrupamento(intencao)
    com_populacao = tem_populacao(con)
    if intencao.medida == "taxa" and not com_populacao:
        raise SemPopulacao
    juncao = JUNCAO_POPULACAO if agrupado_por == "municipio" and com_populacao else ""
    rotulo = AGRUPAMENTOS[agrupado_por] if juncao or agrupado_por != "municipio" else "t.municipio"
    contagem = "COUNT(*)" if intencao.perfil else "COUNT(DISTINCT t.ocorrencia)"
    pop_grupo = "ANY_VALUE(p.populacao)" if juncao else "NULL"
    if agrupado_por == "ano":
        ordem = "g"
    elif intencao.medida == "taxa" and agrupado_por == "municipio":
        ordem = f"{contagem} * 1.0 / {pop_grupo} DESC NULLS LAST, n DESC"
    else:
        ordem = "n DESC"
    linhas = con.execute(
        f"SELECT COALESCE({rotulo}, 'não informado') AS g, {contagem} AS n, {pop_grupo} AS pop "
        f"FROM {tabela} {juncao} WHERE {where} GROUP BY g ORDER BY {ordem} LIMIT {MAX_GRUPOS}",
        params,
    ).fetchall()

    resultado = ResultadoConsulta(
        conjunto=conjunto.nome,
        total=total,
        agrupado_por=agrupado_por,
        grupos=[(str(g), int(n)) for g, n, _ in linhas],
        periodo=(inicio.strftime("%d/%m/%Y") if inicio else "", fim.strftime("%d/%m/%Y") if fim else ""),
        filtros=filtros,
        medida=intencao.medida,
    )
    if intencao.medida == "taxa":
        locais = intencao.municipios or ([intencao.municipio] if intencao.municipio else [])
        pop_total = populacao(con, locais)
        if pop_total is None:
            raise SemPopulacao
        if agrupado_por == "municipio":
            resultado.taxas = {str(g): taxa(int(n), pop) for g, n, pop in linhas if pop}
        elif agrupado_por == "ano":
            resultado.taxas = {str(g): taxa(int(n), pop_total) for g, n, _ in linhas}
        if not intencao.anos:
            resultado.taxa_total = taxa(total, pop_total)
    return resultado
