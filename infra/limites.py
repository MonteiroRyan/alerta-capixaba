"""Limites de uso: por sessão (janela de 1 min) e teto global diário (AD12)."""
import threading
import time
from collections import deque
from datetime import date


class LimiteSessao:
    def __init__(self, maximo: int, janela_s: float = 60):
        self.maximo = maximo
        self.janela_s = janela_s
        self._horarios: deque[float] = deque()

    def permitir(self, agora: float | None = None) -> bool:
        agora = time.monotonic() if agora is None else agora
        while self._horarios and agora - self._horarios[0] >= self.janela_s:
            self._horarios.popleft()
        if len(self._horarios) >= self.maximo:
            return False
        self._horarios.append(agora)
        return True


class TetoGlobal:
    """Compartilhado entre sessões para proteger a cota do Gemini."""

    def __init__(self, maximo_por_dia: int):
        self.maximo = maximo_por_dia
        self._dia = date.today()
        self._usadas = 0
        self._trava = threading.Lock()

    def permitir(self, hoje: date | None = None) -> bool:
        hoje = hoje or date.today()
        with self._trava:
            if hoje != self._dia:
                self._dia, self._usadas = hoje, 0
            if self._usadas >= self.maximo:
                return False
            self._usadas += 1
            return True
