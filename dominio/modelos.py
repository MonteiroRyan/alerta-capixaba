from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

FaixaHoraria = Literal["madrugada", "manha", "tarde", "noite"]
Perfil = Literal["idade", "sexo", "cor_raca"]
Medida = Literal["contagem", "taxa"]
Agrupamento = Literal["bairro", "faixa_horaria", "municipio", "ano"]
MAX_COMPARADOS = 5


class Intencao(BaseModel):
    no_escopo: bool
    tipo_crime: str | None = Field(default=None, max_length=60)
    municipio: str | None = Field(default=None, max_length=60)
    bairro: str | None = Field(default=None, max_length=80)
    ano: int | None = Field(default=None, ge=1900, le=2100)
    faixa_horaria: FaixaHoraria | None = None
    perfil: Perfil | None = None
    agrupar_por: Agrupamento | None = None
    medida: Medida = "contagem"
    anos: list[int] = Field(default_factory=list, max_length=MAX_COMPARADOS)
    municipios: list[str] = Field(default_factory=list, max_length=MAX_COMPARADOS)


@dataclass
class ResultadoConsulta:
    conjunto: str
    total: int
    agrupado_por: str
    grupos: list[tuple[str, int]]
    periodo: tuple[str, str]
    filtros: dict[str, str] = field(default_factory=dict)
    suprimidos: int = 0
    medida: str = "contagem"
    taxa_total: float | None = None
    taxas: dict[str, float] = field(default_factory=dict)
