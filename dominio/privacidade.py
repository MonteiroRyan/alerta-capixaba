"""GuardaPrivacidade: suprime grupos com menos de k registros (AD05)."""
from dataclasses import replace

from dominio.modelos import ResultadoConsulta


def aplicar_guarda(resultado: ResultadoConsulta, k: int) -> ResultadoConsulta:
    visiveis = [(g, n) for g, n in resultado.grupos if n >= k]
    return replace(resultado, grupos=visiveis, suprimidos=len(resultado.grupos) - len(visiveis))
