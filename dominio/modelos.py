"""Entidades do domínio: Intencao e ResultadoConsulta."""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

FaixaHoraria = Literal["madrugada", "manha", "tarde", "noite"]
Perfil = Literal["idade", "sexo", "cor_raca"]


class Intencao(BaseModel):
    """Estrutura devolvida pelo interpretador (validada por schema, AD12)."""
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
    conjunto: str                       # nome legível do conjunto
    total: int                          # ocorrências distintas (RN02)
    agrupado_por: str                   # campo usado nos grupos
    grupos: list[tuple[str, int]]       # (rótulo, contagem)
    periodo: tuple[str, str]            # (data inicial, data final)
    filtros: dict[str, str] = field(default_factory=dict)
    suprimidos: int = 0                 # grupos ocultados pela guarda de privacidade
