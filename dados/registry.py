"""Carrega o registry.yaml em objetos ConjuntoDados."""
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ConjuntoDados:
    id: str
    nome: str
    familia: str            # "A" (patrimônio) ou "B" (pessoa)
    resource_id: str
    arquivo: str
    campos: dict[str, str]  # campo canônico -> coluna do CSV
    dataset_id: str = ""

    @property
    def url(self) -> str:
        """Página do recurso no portal dados.es.gov.br."""
        return f"https://dados.es.gov.br/dataset/{self.dataset_id}/resource/{self.resource_id}"

    @property
    def url_download(self) -> str:
        """Download direto do CSV no portal (padrão CKAN)."""
        return f"{self.url}/download/{self.arquivo}"

    @property
    def tem_perfil(self) -> bool:
        return self.familia == "B"


def carregar_registry(caminho: Path) -> dict[str, ConjuntoDados]:
    with open(caminho, encoding="utf-8") as f:
        bruto = yaml.safe_load(f)["conjuntos"]
    return {cid: ConjuntoDados(id=cid, **dados) for cid, dados in bruto.items()}


@dataclass(frozen=True)
class IndicadorMapa:
    id: str
    nome: str
    grupo: str              # "Crimes contra a vida", "Roubos", ...
    cor: str                # tom mais escuro da escala do mapa


def carregar_mapa(caminho: Path) -> dict[str, IndicadorMapa]:
    with open(caminho, encoding="utf-8") as f:
        bruto = yaml.safe_load(f)["mapa"]
    return {iid: IndicadorMapa(id=iid, **dados) for iid, dados in bruto.items()}
