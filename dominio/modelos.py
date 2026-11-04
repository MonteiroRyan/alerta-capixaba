from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

FaixaHoraria = Literal["madrugada", "manha", "tarde", "noite"]
Perfil = Literal["idade", "sexo", "cor_raca"]


class Intencao(BaseModel):
    no_escopo: bool
    tipo_crime: str | None = Field(default=None, max_length=60)
    municipio: str | None = Field(default=None, max_length=60)
    bairro: str | None = Field(default=None, max_length=80)
    ano: int | None = Field(default=None, ge=1900, le=2100)
    faixa_horaria: FaixaHoraria | None = None
    perfil: Perfil | None = None
    agrupar_por: Literal["bairro", "faixa_horaria"] | None = None


@dataclass
class ResultadoConsulta:
    conjunto: str
    total: int
    agrupado_por: str
    grupos: list[tuple[str, int]]
    periodo: tuple[str, str]
    filtros: dict[str, str] = field(default_factory=dict)
    suprimidos: int = 0
