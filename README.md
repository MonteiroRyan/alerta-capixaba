# Alerta Capixaba

Chatbot para consulta dos dados abertos de segurança pública do Espírito Santo (SESP).

## Rodar localmente

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # preencha GEMINI_API_KEY
.venv\Scripts\python -m streamlit run app.py
```

O app abre em http://localhost:8501. Na inicialização, o ETL baixa os 16 CSV do portal
dados.es.gov.br para `base/csv/` (reaproveitados por 24 h; se o portal falhar, usa a cópia
de `dataset/`) e gera a base Parquet em `base/`.

## Testes

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest testes
```

## Mapa

O mapa usa cópias locais do IBGE em `dados/ibge/`: a malha municipal do ES
(API de malhas v3, baixada em 08/10/2026) e a população do Censo 2022 (SIDRA, tabela 4709).
Ao escolher um município, o mapa mostra os bairros oficiais da malha de bairros do Censo 2022
(17 municípios do ES). O arquivo `malha-bairros-es-cd2022.geojson` é gerado por
`dados/ibge/gerar_malha_bairros.py` a partir do GeoPackage do IBGE.
