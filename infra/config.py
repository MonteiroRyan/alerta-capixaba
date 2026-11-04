"""Parâmetros do sistema: privacidade, cache, modelo e limites de segurança."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_CSV = RAIZ / "dataset"          # cópia local dos CSV da SESP (reserva se o portal falhar)
DIR_DOWNLOAD = RAIZ / "base" / "csv"  # CSV baixados do portal da SESP pelo ETL
DIR_BASE = RAIZ / "base"            # base Parquet gerada pelo ETL
ARQUIVO_REGISTRY = RAIZ / "dados" / "registry.yaml"

K_MINIMO = 5                        # limiar de k-anonimato (AD05)
TTL_CACHE_S = 24 * 3600             # validade do cache da base (AD06)

# Conferir o identificador na documentação do Gemini; pode ser sobrescrito
# por GEMINI_MODELO em .streamlit/secrets.toml ou variável de ambiente.
MODELO_GEMINI = "gemini-3.5-flash-lite"

# Limites de uso (AD12)
MAX_CARACTERES = 300
MAX_PERGUNTAS_POR_MINUTO = 10
TETO_GLOBAL_POR_DIA = 500

# Interface
COR_PRIMARIA = "#0096E1"
ARQUIVO_AVALIACOES = RAIZ / "avaliacoes.jsonl"   # útil / não útil (OE5)

# Mapa (IBGE, cópias locais para funcionar offline)
DIR_IBGE = RAIZ / "dados" / "ibge"
ARQUIVO_MALHA = DIR_IBGE / "malha-municipios-es-2026-10-08.geojson"   # API de malhas v3
ARQUIVO_POPULACAO = DIR_IBGE / "populacao-censo-2022-es.csv"           # SIDRA, tabela 4709
ARQUIVO_MALHA_BAIRROS = DIR_IBGE / "malha-bairros-es-cd2022.geojson"   # Censo 2022, 17 municípios
