import logging
import re
import shutil
import time
from pathlib import Path

import pandas as pd
import requests

from dados.registry import ConjuntoDados

log = logging.getLogger(__name__)

CAMPOS_CANONICOS = [
    "ocorrencia", "data_fato", "hora_fato", "faixa_horaria", "municipio",
    "bairro", "tipo_local", "tipo_crime", "familia", "tipo_objeto", "marca",
    "modelo", "idade", "sexo", "cor_raca",
]

AUSENTES = {"", "S/I", "INDETERMINADA", "INDETERMINADO", "NÃO INFORMADO", "PREJUDICADO"}


def normalizar_texto(serie: pd.Series) -> pd.Series:
    s = serie.astype("string").str.upper().str.strip()
    s = s.str.replace(r"\s+", " ", regex=True)
    return s.str.replace(r"^\d+\s*-\s*", "", regex=True)


def faixa_horaria(hora: str | None) -> str:
    if not isinstance(hora, str) or not re.match(r"^\d{1,2}:\d{2}", hora.strip()):
        return "indeterminada"
    h = int(hora.strip().split(":")[0])
    if h < 6:
        return "madrugada"
    if h < 12:
        return "manha"
    if h < 18:
        return "tarde"
    return "noite"


def ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str)


def transformar(bruto: pd.DataFrame, conjunto: ConjuntoDados) -> pd.DataFrame:
    df = pd.DataFrame({canon: bruto[col] for canon, col in conjunto.campos.items()})
    df = df.reindex(columns=CAMPOS_CANONICOS)

    df["tipo_crime"] = conjunto.id
    df["familia"] = conjunto.familia
    df["data_fato"] = pd.to_datetime(df["data_fato"], format="%d/%m/%Y", errors="coerce").dt.date
    df["faixa_horaria"] = df["hora_fato"].map(faixa_horaria)
    for campo in ["municipio", "bairro", "tipo_local", "tipo_objeto", "marca", "modelo", "sexo", "cor_raca"]:
        df[campo] = normalizar_texto(df[campo])
    for campo in ["sexo", "cor_raca"]:
        df[campo] = df[campo].where(~df[campo].isin(AUSENTES))
    df["idade"] = pd.to_numeric(df["idade"], errors="coerce").astype("Int64")

    return df.drop_duplicates().reset_index(drop=True)


def obter_csvs(conjuntos: dict[str, ConjuntoDados], dir_cache: Path, dir_reserva: Path, validade_s: float) -> None:
    dir_cache.mkdir(parents=True, exist_ok=True)
    for conjunto in conjuntos.values():
        destino = dir_cache / conjunto.arquivo
        if destino.exists() and time.time() - destino.stat().st_mtime < validade_s:
            continue
        try:
            resposta = requests.get(conjunto.url_download, timeout=120)
            resposta.raise_for_status()
            temporario = destino.with_suffix(".tmp")
            temporario.write_bytes(resposta.content)
            temporario.replace(destino)
            log.info("Download %s: %d bytes", conjunto.arquivo, len(resposta.content))
        except requests.RequestException:
            log.warning("Falha ao baixar %s do portal da SESP", conjunto.arquivo, exc_info=True)
            reserva = dir_reserva / conjunto.arquivo
            if not destino.exists() and reserva.exists():
                shutil.copy2(reserva, destino)


def preparar_base(conjuntos: dict[str, ConjuntoDados], dir_csv: Path, dir_base: Path) -> dict[str, Path]:
    dir_base.mkdir(parents=True, exist_ok=True)
    gerados = {}
    for conjunto in conjuntos.values():
        origem = dir_csv / conjunto.arquivo
        if not origem.exists():
            log.error("ETL %s: CSV indisponível, conjunto ignorado", conjunto.id)
            continue
        destino = dir_base / f"{conjunto.id}.parquet"
        df = transformar(ler_csv(origem), conjunto)
        df.to_parquet(destino, index=False)
        log.info("ETL %s: %d registros -> %s", conjunto.id, len(df), destino.name)
        gerados[conjunto.id] = destino
    return gerados


def preparar_populacao(arquivo_populacao: Path, dir_base: Path) -> dict[str, Path]:
    dir_base.mkdir(parents=True, exist_ok=True)
    destino = dir_base / "populacao.parquet"
    pd.read_csv(arquivo_populacao, dtype={"codigo_ibge": str}).to_parquet(destino, index=False)
    return {"populacao": destino}
