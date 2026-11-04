from dominio.modelos import ResultadoConsulta
from dominio.privacidade import aplicar_guarda


def test_suprime_grupos_abaixo_de_k():
    r = ResultadoConsulta("X", 10, "sexo", [("MASCULINO", 8), ("FEMININO", 2)], ("", ""))
    r2 = aplicar_guarda(r, 5)
    assert r2.grupos == [("MASCULINO", 8)]
    assert r2.suprimidos == 1
