"""RepositorioSESP: carrega a base Parquet no DuckDB e trava a conexão."""
import unicodedata
from pathlib import Path

import duckdb


def chave(texto: str) -> str:
    """Forma comparável de um nome de lugar: maiúsculas, sem acentos e espaços extras."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def abrir_conexao(parquets: dict[str, Path]) -> duckdb.DuckDBPyConnection:
    """Carrega cada Parquet em uma tabela em memória e desativa o acesso externo (AD12)."""
    con = duckdb.connect(":memory:")
    for cid, caminho in parquets.items():
        # cid e caminho vêm do registry e da config, nunca do usuário.
        con.execute(f'CREATE TABLE "{cid}" AS SELECT * FROM read_parquet(\'{caminho.as_posix()}\')')
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def locais(con: duckdb.DuckDBPyConnection, cid: str) -> dict:
    """Municípios e bairros existentes no conjunto (indexados pela chave sem acento) e anos cobertos."""
    resultado = {}
    for campo in ("municipio", "bairro"):
        nomes = con.execute(f'SELECT DISTINCT {campo} FROM "{cid}" WHERE {campo} IS NOT NULL').fetchall()
        resultado[campo] = {chave(n): n for (n,) in nomes}
    anos = con.execute(f'SELECT DISTINCT year(data_fato) FROM "{cid}" WHERE data_fato IS NOT NULL').fetchall()
    resultado["anos"] = sorted(a for (a,) in anos)
    return resultado
