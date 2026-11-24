from dados.registry import ConjuntoDados
from dados.repositorio import chave
from dominio.modelos import Intencao

ESTADO = {"ES", "ESPIRITO SANTO", "ESTADO DO ESPIRITO SANTO"}
SEM_TAXA = ("A taxa por 100 mil habitantes só pode ser calculada para municípios e para o estado, "
            "porque a população do Censo 2022 não é divulgada por {recorte}. "
            "Posso mostrar o número de ocorrências; as taxas por município estão no mapa.")


class RecorteInvalido(Exception):

    def __init__(self, mensagem: str, motivo: str):
        super().__init__(mensagem)
        self.motivo = motivo


def unificar(intencao: Intencao) -> Intencao:
    """Junta o campo simples e a lista (ano/anos, municipio/municipios) e define o agrupamento."""
    anos = sorted(set(intencao.anos) | ({intencao.ano} if intencao.ano else set()))
    municipios = list(dict.fromkeys(
        m for m in intencao.municipios + ([intencao.municipio] if intencao.municipio else [])
        if chave(m) not in ESTADO))
    ajustes = {"ano": anos[0] if len(anos) == 1 else None, "anos": anos if len(anos) > 1 else [],
               "municipio": municipios[0] if len(municipios) == 1 else None,
               "municipios": municipios if len(municipios) > 1 else []}
    if not intencao.agrupar_por and not intencao.perfil:
        if len(municipios) > 1:
            ajustes["agrupar_por"] = "municipio"
        elif len(anos) > 1:
            ajustes["agrupar_por"] = "ano"
    return intencao.model_copy(update=ajustes)


def validar_taxa(intencao: Intencao) -> None:
    if intencao.medida != "taxa":
        return
    if intencao.bairro or intencao.agrupar_por == "bairro":
        raise RecorteInvalido(SEM_TAXA.format(recorte="bairro"), "taxa")
    if intencao.faixa_horaria or intencao.agrupar_por == "faixa_horaria":
        raise RecorteInvalido(SEM_TAXA.format(recorte="horário do fato"), "taxa")
    if intencao.perfil:
        raise RecorteInvalido(SEM_TAXA.format(recorte="perfil das vítimas"), "taxa")


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

    intencao = unificar(intencao)
    validar_taxa(intencao)

    def localizar(campo: str, valor: str) -> str:
        nome = locais[conjunto.id][campo].get(chave(valor))
        if nome is None:
            rotulo = "o município" if campo == "municipio" else "o bairro"
            raise RecorteInvalido(
                f"Não encontrei {rotulo} \"{valor}\" nos dados de {conjunto.nome.lower()}. "
                "Confira a grafia ou veja um recorte mais amplo.",
                campo,
            )
        return nome

    ajustes = {campo: localizar(campo, getattr(intencao, campo))
               for campo in ("municipio", "bairro") if getattr(intencao, campo)}
    if intencao.municipios:
        ajustes["municipios"] = [localizar("municipio", m) for m in intencao.municipios]

    anos = locais[conjunto.id]["anos"]
    fora = [a for a in (intencao.anos or [intencao.ano]) if a and a not in anos]
    if fora:
        raise RecorteInvalido(f"Os dados de {conjunto.nome.lower()} cobrem apenas de {anos[0]} a {anos[-1]}.", "ano")
    if intencao.medida == "taxa" and not intencao.ano and not intencao.anos:
        ajustes["ano"] = anos[-1]
    return conjunto, intencao.model_copy(update=ajustes)
