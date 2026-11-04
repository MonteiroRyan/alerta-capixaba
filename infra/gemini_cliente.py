"""Wrapper do SDK google-genai."""
from google import genai
from google.genai import types


class ClienteGemini:
    def __init__(self, api_key: str, modelo: str):
        # Novas tentativas para sobrecarga temporária da API (429/503), RNF04.
        repeticao = types.HttpRetryOptions(attempts=3, initial_delay=2, http_status_codes=[429, 500, 503])
        self._cliente = genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=repeticao))
        self._modelo = modelo

    def gerar_json(self, instrucao: str, texto: str, schema: dict) -> str:
        resposta = self._cliente.models.generate_content(
            model=self._modelo,
            contents=texto,
            config=types.GenerateContentConfig(
                system_instruction=instrucao,
                response_mime_type="application/json",
                response_json_schema=schema,
                temperature=0,
            ),
        )
        return resposta.text

    def gerar_texto(self, instrucao: str, texto: str) -> str:
        resposta = self._cliente.models.generate_content(
            model=self._modelo,
            contents=texto,
            config=types.GenerateContentConfig(system_instruction=instrucao, temperature=0.2),
        )
        return resposta.text
