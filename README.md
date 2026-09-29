# 🗺️ Gauden Comercial — App de Prospecção Varejo

App Streamlit para prospecção de pontos de venda em Curitiba.
Consulta ao vivo na Google Places API + roteirização de até 20 pontos.

## Funcionalidades

- 🔍 **Busca por região, bairro e canal** (Açougue, Bar, Restaurante, Adega, Padaria)
- 🗺️ **Mapa interativo** com pins coloridos por canal
- 📋 **Lista** com cards detalhados (telefone, site, horários)
- 🚗 **Roteirização** — até 20 paradas por rota, otimizadas por proximidade
- 📥 **Exportação Excel** com estabelecimentos + roteiro

---

## Deploy no Streamlit Cloud (gratuito)

### 1. Crie um repositório no GitHub

```
app_gauden/
├── app.py
├── places_api.py
├── roteirizador.py
├── requirements.txt
└── .streamlit/
    └── config.toml
```

### 2. Acesse share.streamlit.io

- Conecte sua conta GitHub
- Selecione o repositório
- Main file: `app.py`
- Clique em **Deploy**

### 3. Configure a chave da API

No Streamlit Cloud, vá em:
**Settings → Secrets** e cole:

```toml
GOOGLE_MAPS_KEY = "AIzaSy..."
```

Ou ao abrir o app, cole a chave diretamente no campo da sidebar.

---

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Crie o arquivo `.streamlit/secrets.toml`:
```toml
GOOGLE_MAPS_KEY = "AIzaSy..."
```

---

## Estrutura dos arquivos

| Arquivo | Descrição |
|---------|-----------|
| `app.py` | App principal Streamlit — UI, abas, mapa, lista, rotas, exportação |
| `places_api.py` | Módulo de consulta à Google Places API (Text Search + Place Details) |
| `roteirizador.py` | Algoritmo de roteirização por proximidade (Nearest Neighbor) |
| `requirements.txt` | Dependências Python |
| `.streamlit/config.toml` | Tema escuro customizado |

---

## Canais mapeados

| Canal | Termos de busca |
|-------|----------------|
| C1 Açougue / Parrilla | açougue, casa de carnes, parrilla, steak house... |
| C2 Bar / Pub | bar, pub, brewpub, cervejaria, boteco... |
| C3 Restaurante | restaurante, gastronomia, bistrô, churrascaria... |
| C4 Empório / Adega | empório, adega, distribuidora de bebidas... |
| C5 Padaria / Mercado | padaria, panificadora, pão artesanal, mini mercado... |

---

Desenvolvido para **Gauden Comercial · Curitiba, PR**
