"""Orquestrador: interpretação -> roteamento -> consulta -> privacidade -> resposta."""
import logging
from dataclasses import dataclass, field
from datetime import datetime

import duckdb

from dados.registry import ConjuntoDados
from dados.repositorio import locais
from dominio import sugestoes
from dominio.consulta import consultar
from dominio.interpretador import interpretar
from dominio.modelos import Intencao, ResultadoConsulta
from dominio.privacidade import aplicar_guarda
from dominio.resposta import redigir
from dominio.roteador import RecorteInvalido, rotear
from infra import config

log = logging.getLogger(__name__)

# Mensagens padronizadas (Quadro 5 da especificação da interface).
FORA_DO_ESCOPO = "Respondo só perguntas sobre estatísticas criminais publicadas pela SESP-ES. Posso mostrar, por exemplo:"
INDISPONIVEL = ("Não foi possível consultar os dados da SESP-ES agora. "
                "Sua pergunta foi mantida; tente de novo em alguns minutos.")


@dataclass
class Resposta:
    texto: str
    tipo: str = "resposta"      # resposta | esclarecimento | fora_escopo | erro | aviso
    resultado: ResultadoConsulta | None = None
    intencao: Intencao | None = None
    conjunto: ConjuntoDados | None = None
    opcoes: list[str] = field(default_factory=list)   # perguntas prontas para clicar
    consultado_em: datetime = field(default_factory=datetime.now)


class Orquestrador:
    def __init__(self, con: duckdb.DuckDBPyConnection, conjuntos: dict[str, ConjuntoDados], cliente):
        self.con = con
        self.conjuntos = conjuntos
        self.cliente = cliente
        self.locais = {cid: locais(con, cid) for cid in conjuntos}

    def responder(self, pergunta: str) -> Resposta:
        pergunta = pergunta.strip()
        if not pergunta:
            return Resposta("Escreva uma pergunta.", "aviso")
        if len(pergunta) > config.MAX_CARACTERES:
            return Resposta(f"A pergunta deve ter até {config.MAX_CARACTERES} caracteres.", "aviso")
        if self.cliente is None:
            return Resposta("O assistente ainda não está configurado: falta a chave da API do Gemini.", "erro")

        try:
            intencao = interpretar(self.cliente, pergunta, self.conjuntos)
        except Exception:
            log.exception("Falha ao interpretar a pergunta")
            return Resposta(INDISPONIVEL, "erro")

        if not intencao.no_escopo:
            return Resposta(FORA_DO_ESCOPO, "fora_escopo", opcoes=sugestoes.FORA_DO_ESCOPO)

        try:
            conjunto, intencao = rotear(intencao, self.conjuntos, self.locais)
            # Cursor próprio por pergunta: a conexão é compartilhada entre as sessões do Streamlit.
            resultado = aplicar_guarda(consultar(self.con.cursor(), conjunto, intencao), config.K_MINIMO)
            anos = self.locais[conjunto.id]["anos"]
            return Resposta(redigir(self.cliente, resultado), "resposta", resultado, intencao, conjunto,
                            sugestoes.continuacoes(conjunto, intencao, self.conjuntos, anos))
        except RecorteInvalido as e:
            anos = self.locais.get(intencao.tipo_crime or "", {}).get("anos")
            opcoes = sugestoes.para_recorte(e.motivo, intencao, pergunta, self.conjuntos, anos)
            return Resposta(str(e), "esclarecimento", intencao=intencao, opcoes=opcoes)
        except Exception:
            log.exception("Falha ao processar a pergunta")
            return Resposta(INDISPONIVEL, "erro")

    def cobertura(self) -> dict:
        """Resumo para a barra lateral: municípios cobertos e período dos dados."""
        municipios = set().union(*(set(l["municipio"].values()) for l in self.locais.values()))
        anos = sorted(set().union(*(l["anos"] for l in self.locais.values())))
        return {"municipios": len(municipios), "anos": (anos[0], anos[-1])}
