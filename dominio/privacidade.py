from dataclasses import replace

from dominio.modelos import ResultadoConsulta


def aplicar_guarda(resultado: ResultadoConsulta, k: int) -> ResultadoConsulta:
    visiveis = [(g, n) for g, n in resultado.grupos if n >= k]
    taxas = {g: t for g, t in resultado.taxas.items() if g in dict(visiveis)}
    return replace(resultado, grupos=visiveis, taxas=taxas, suprimidos=len(resultado.grupos) - len(visiveis))
