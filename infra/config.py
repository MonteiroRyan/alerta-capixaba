from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_CSV = RAIZ / "dataset"
DIR_DOWNLOAD = RAIZ / "base" / "csv"
DIR_BASE = RAIZ / "base"
ARQUIVO_REGISTRY = RAIZ / "dados" / "registry.yaml"

K_MINIMO = 5
TTL_CACHE_S = 24 * 3600

MODELO_GEMINI = "gemini-3.5-flash-lite"

MAX_CARACTERES = 300
MAX_PERGUNTAS_POR_MINUTO = 10
TETO_GLOBAL_POR_DIA = 500

COR_PRIMARIA = "#0096E1"
ARQUIVO_AVALIACOES = RAIZ / "avaliacoes.jsonl"

DIR_IBGE = RAIZ / "dados" / "ibge"
ARQUIVO_MALHA = DIR_IBGE / "malha-municipios-es-2026-10-08.geojson"
ARQUIVO_POPULACAO = DIR_IBGE / "populacao-censo-2022-es.csv"
ARQUIVO_MALHA_BAIRROS = DIR_IBGE / "malha-bairros-es-cd2022.geojson"
