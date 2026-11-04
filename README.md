# Alerta Capixaba

Interface conversacional para consulta dos dados abertos de segurança pública do Espírito Santo.

Trabalho de Conclusão de Curso de Sistemas de Informação da UniSales (Vitória/ES).

- **Autor:** Ryan Monteiro Nascimento
- **Orientador:** Prof. Vito Rodrigues Franzosi

## Sobre o trabalho

A Secretaria de Estado da Segurança Pública e Defesa Social do Espírito Santo (SESP-ES) publica
os registros de ocorrências no portal [dados.es.gov.br](https://dados.es.gov.br), mas em arquivos
CSV que exigem conhecimento técnico para serem lidos. O Alerta Capixaba busca reduzir essa
distância entre a transparência dos dados e o acesso real do cidadão: qualquer pessoa faz uma
pergunta em português, como "Quantos roubos de celular houve em Vitória em 2025?", e recebe a
resposta com o número, um gráfico e o link para a fonte oficial.

## Como funciona

1. **Dados:** ao iniciar, o sistema baixa 16 conjuntos da SESP (homicídios e feminicídios,
   violência doméstica, roubos e furtos), de 2023 a 2025, nos 78 municípios do estado, e os
   converte para Parquet. Se o portal estiver fora do ar, usa a cópia guardada em `dataset/`.
2. **Interpretação:** o modelo Google Gemini lê a pergunta e extrai apenas os filtros (crime,
   município, bairro e período).
3. **Consulta:** o sistema monta e executa a consulta no DuckDB. O modelo de linguagem não gera
   números: eles sempre vêm da base oficial.
4. **Resposta:** o chat mostra o resultado com gráfico, tabela, download em CSV, fonte e o
   painel "Como entendi sua pergunta". Ao lado, um mapa mostra a taxa por 100 mil habitantes
   de cada município (população do Censo 2022 do IBGE) e os bairros oficiais ao escolher um
   município.

O protótipo também aplica cuidados de privacidade (LGPD) aos dados de vítimas e limita o
tamanho e a frequência das perguntas.

**Tecnologias:** Python 3.12, Streamlit, Google Gemini API, pandas, DuckDB e Plotly.

## Rodar localmente

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # preencha GEMINI_API_KEY
.venv\Scripts\python -m streamlit run app.py
```

O app abre em http://localhost:8501.

## Testes

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest testes
```

## Fontes de dados

- Ocorrências: SESP-ES, portal de dados abertos [dados.es.gov.br](https://dados.es.gov.br).
- Malhas de municípios e de bairros e população: IBGE (Censo 2022), com cópias em `dados/ibge/`.
