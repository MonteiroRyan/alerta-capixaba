from dados.registry import ConjuntoDados
from dados.repositorio import chave
from dominio.modelos import Intencao

ESTADO = {"ES", "ESPIRITO SANTO", "ESTADO DO ESPIRITO SANTO"}


class RecorteInvalido(Exception):

    def __init__(self, mensagem: str, motivo: str):
        super().__init__(mensagem)
        self.motivo = motivo


def rotear(intencao: Intencao, conjuntos: dict[str, ConjuntoDados],
           locais: dict[str, dict]) -> tuple[ConjuntoDados, Intencao]:
    conjunto = conjuntos.get(intencao.tipo_crime or "")
    if conjunto is None:
        raise RecorteInvalido("Sobre qual tipo de crime é a sua pergunta?", "tipo")

    if intencao.perfil and not conjunto.tem_perfil:
        raise RecorteInvalido(
            f"Os dados de {conjunto.nome.lower()} não trazem o perfil da vítima. "
            "Posso mostrar a distribuição por bairro ou por faixa horária.",
            "perfil",
        )

    ajustes = {}
    if intencao.municipio and chave(intencao.municipio) in ESTADO:
        intencao = intencao.model_copy(update={"municipio": None})
    for campo in ("municipio", "bairro"):
        valor = getattr(intencao, campo)
        if valor:
            nome = locais[conjunto.id][campo].get(chave(valor))
            if nome is None:
                rotulo = "o município" if campo == "municipio" else "o bairro"
                raise RecorteInvalido(
                    f"Não encontrei {rotulo} \"{valor}\" nos dados de {conjunto.nome.lower()}. "
                    "Confira a grafia ou veja um recorte mais amplo.",
                    campo,
                )
            ajustes[campo] = nome

    anos = locais[conjunto.id]["anos"]
    if intencao.ano and intencao.ano not in anos:
        raise RecorteInvalido(f"Os dados de {conjunto.nome.lower()} cobrem apenas de {anos[0]} a {anos[-1]}.", "ano")
    return conjunto, intencao.model_copy(update=ajustes)
