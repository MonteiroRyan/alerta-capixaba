"""Mapa por município: taxas por 100 mil habitantes e classes por quantis."""
import duckdb
import numpy as np
import pandas as pd

POR_HABITANTES = 100_000
N_CLASSES = 5
# Mesma forma comparável de dados.repositorio.chave, em SQL: sem acentos, maiúsculas, espaços simples.
CHAVE_SQL = r"regexp_replace(trim(upper(strip_accents({}))), '\s+', ' ', 'g')"


def criar_tabela_mapa(con: duckdb.DuckDBPyConnection, indicadores: list[str]) -> None:
    """Ocorrências distintas por município (código IBGE) e ano, a partir das tabelas do chat.

    O município da SESP casa com o da população pela forma sem acento (CHAVE_SQL).
    """
    mun_sesp, mun_ibge = CHAVE_SQL.format("t.municipio"), CHAVE_SQL.format("p.municipio")
    # Os ids vêm do registry (nomes das tabelas), nunca do usuário.
    partes = [
        f"SELECT '{i}' AS indicador, p.codigo_ibge, year(t.data_fato) AS ano, "
        f'COUNT(DISTINCT t.ocorrencia) AS ocorrencias FROM "{i}" t '
        f"JOIN populacao p ON {mun_sesp} = {mun_ibge} WHERE t.data_fato IS NOT NULL GROUP BY ALL"
        for i in indicadores
    ]
    con.execute("CREATE TABLE mapa_ocorrencias AS " + " UNION ALL ".join(partes))


def taxas(con: duckdb.DuckDBPyConnection, indicador: str, ano: int) -> pd.DataFrame:
    """Todos os municípios (inclusive sem registro) com ocorrências e taxa no ano."""
    return con.execute(
        "SELECT p.codigo_ibge, p.municipio, COALESCE(o.ocorrencias, 0) AS ocorrencias, "
        f"COALESCE(o.ocorrencias, 0) * {POR_HABITANTES}.0 / p.populacao AS taxa "
        "FROM populacao p LEFT JOIN mapa_ocorrencias o "
        "ON o.codigo_ibge = p.codigo_ibge AND o.indicador = ? AND o.ano = ? ORDER BY p.codigo_ibge",
        [indicador, ano],
    ).df()


def historico(con: duckdb.DuckDBPyConnection, indicador: str, codigo_ibge: str, anos: list[int]) -> pd.DataFrame:
    """Ocorrências e taxa de um município em cada ano pedido (0 quando não há registro)."""
    return con.execute(
        "SELECT a.ano, COALESCE(o.ocorrencias, 0) AS ocorrencias, "
        f"COALESCE(o.ocorrencias, 0) * {POR_HABITANTES}.0 / p.populacao AS taxa "
        "FROM (SELECT unnest(?::INTEGER[]) AS ano) a CROSS JOIN populacao p "
        "LEFT JOIN mapa_ocorrencias o ON o.codigo_ibge = p.codigo_ibge AND o.ano = a.ano AND o.indicador = ? "
        "WHERE p.codigo_ibge = ? ORDER BY a.ano",
        [anos, indicador, codigo_ibge],
    ).df()


def limites(valores: pd.Series, n: int = N_CLASSES) -> list[float]:
    """Limites superiores das classes por quantis; quantis repetidos viram uma só classe."""
    return sorted(set(np.quantile(valores, [(i + 1) / n for i in range(n)]).tolist()))


def classificar(valores: pd.Series, lims: list[float]) -> np.ndarray:
    """Índice da classe de cada valor: a primeira cujo limite superior é >= valor."""
    return np.searchsorted(lims, valores, side="left")


def escala(cor: str, n: int = N_CLASSES) -> list[str]:
    """Tons de claro a escuro, misturando a cor do indicador com branco."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    pesos = [0.12 + 0.88 * i / (n - 1) for i in range(n)]
    return ["#%02X%02X%02X" % tuple(round(255 - (255 - c) * p) for c in (r, g, b)) for p in pesos]


def _area(anel: list) -> float:
    """Área com sinal (fórmula do laço): positiva se o anel é anti-horário."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anel, anel[1:])) / 2


def orientar(malha: dict) -> dict:
    """Contorno externo no sentido horário e furos no anti-horário, como o Plotly (d3) espera.

    A malha do IBGE segue a RFC 7946 (externo anti-horário); sem isso o d3 pinta o globo todo.
    """
    for feicao in malha["features"]:
        geo = feicao["geometry"]
        poligonos = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        for poligono in poligonos:
            for i, anel in enumerate(poligono):
                if (_area(anel) > 0) == (i == 0):
                    anel.reverse()
    return malha


def sem_ilhas_oceanicas(malha: dict, lon_max: float = -39.0) -> dict:
    """Remove as partes a leste de lon_max: Trindade e Martim Vaz, de Vitória, a ~1.100 km da costa.

    Com elas, o enquadramento automático do mapa encolheria o estado.
    """
    for feicao in malha["features"]:
        geo = feicao["geometry"]
        if geo["type"] == "MultiPolygon":
            geo["coordinates"] = [p for p in geo["coordinates"] if min(x for x, _ in p[0]) < lon_max]
    return malha


# ---- Bairros (17 municípios com malha oficial do IBGE) ---------------------



def ocorrencias_bairros(con: duckdb.DuckDBPyConnection, indicador: str, municipio: str,
                        anos: list[int]) -> pd.DataFrame:
    """Ocorrências distintas por bairro (pela chave sem acento) e ano em um município."""
    bairro, mun = CHAVE_SQL.format("bairro"), CHAVE_SQL.format("municipio")
    # indicador vem do registry (nome da tabela), nunca do usuário.
    return con.execute(
        f'SELECT {bairro} AS chave, year(data_fato) AS ano, COUNT(DISTINCT ocorrencia) AS ocorrencias '
        f'FROM "{indicador}" WHERE {mun} = ? AND bairro IS NOT NULL AND year(data_fato) IN (SELECT unnest(?::INTEGER[])) '
        "GROUP BY ALL",
        [municipio, anos],
    ).df()


def bairros_do_municipio(malha_bairros: dict, codigo_ibge: str) -> dict:
    """Recorte da malha de bairros com só as feições de um município."""
    return {"type": "FeatureCollection",
            "features": [f for f in malha_bairros["features"] if f["properties"]["cd_mun"] == codigo_ibge]}
