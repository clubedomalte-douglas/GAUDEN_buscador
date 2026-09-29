"""
places_api.py — Módulo de consulta à Google Places API
Gauden Comercial · App de Prospecção Varejo Curitiba
"""
import requests
import time
import streamlit as st

BASE_URL = "https://maps.googleapis.com/maps/api"
CWB_LAT  = -25.4284
CWB_LNG  = -49.2733

# ── Bairros de Curitiba por região ──────────────────────────────
REGIOES = {
    "R1 — Norte": [
        "Alto da XV", "Alto da Glória", "Hugo Lange", "Jardim Social",
        "Bairro Alto", "Bacacheri", "Atuba", "Tingui", "Juvevê",
        "Centro Cívico", "Ahú", "Cabral", "São Lourenço", "Boa Vista",
        "Barreirinha", "Abranches", "Cachoeira", "Santa Cândida", "Tarumã", "Taboão",
    ],
    "R2 — Centro-Oeste": [
        "Centro", "São Francisco", "Bom Retiro", "Pilarzinho", "Vista Alegre",
        "Mercês", "Bigorrilho", "Campina do Siqueira", "Mossunguê",
        "Campo Comprido", "São Brás", "Santa Felicidade", "Guaíra",
        "Parolin", "Vila Izabel", "São João", "Lamenha Pequena",
    ],
    "R3 — Sul Centro-Sul": [
        "Batel", "Seminário", "Água Verde", "Rebouças", "Cristo Rei",
        "Capão da Imbuia", "Jardim das Américas", "Portão", "Fanny",
        "Guabirotuba", "Lindóia", "Santa Quitéria", "Prado Velho",
        "Jardim Botânico",
    ],
    "R4 — Sul Leste": [
        "CIC", "Capão Raso", "Xaxim", "Boqueirão", "Vila Hauer",
        "Alto Boqueirão", "Uberaba", "Tatuquara", "Umbará", "Novo Mundo",
        "Cajuru", "Pinheirinho", "Sítio Cercado", "Campo de Santana",
        "Fazendinha", "Orleans",
    ],
}

# Mapa bairro → região
BAIRRO_REGIAO = {b: r for r, bs in REGIOES.items() for b in bs}

# ── Termos de busca por canal ────────────────────────────────────
CANAIS = {
    "C1 — Açougue / Parrilla": [
        "açougue", "casa de carnes", "parrilla", "boutique de carnes",
        "carnes nobres", "frigorífico", "steak house", "meat house",
    ],
    "C2 — Bar / Pub": [
        "bar", "pub", "brewpub", "cervejaria artesanal", "boteco", "choperia",
    ],
    "C3 — Restaurante": [
        "restaurante", "gastronomia", "bistrô", "churrascaria",
    ],
    "C4 — Empório / Adega": [
        "empório", "adega", "distribuidora de bebidas", "wine bar",
    ],
    "C5 — Padaria / Mercado": [
        "padaria", "panificadora", "pão artesanal", "mini mercado", "mercearia",
    ],
}

COR_CANAL = {
    "C1 — Açougue / Parrilla":  "#ff9090",
    "C2 — Bar / Pub":            "#90b8ff",
    "C3 — Restaurante":          "#90ffaa",
    "C4 — Empório / Adega":      "#ffd090",
    "C5 — Padaria / Mercado":    "#e890ff",
}

ICONE_CANAL = {
    "C1 — Açougue / Parrilla":  "🥩",
    "C2 — Bar / Pub":            "🍺",
    "C3 — Restaurante":          "🍽️",
    "C4 — Empório / Adega":      "🍷",
    "C5 — Padaria / Mercado":    "🥖",
}


def _get_key() -> str:
    """Retorna a chave da API do secrets do Streamlit."""
    try:
        return st.secrets["GOOGLE_MAPS_KEY"]
    except Exception:
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def text_search(query: str, raio: int = 15000) -> list[dict]:
    """
    Faz Text Search na Places API e retorna lista de resultados.
    Cache de 1 hora para não repetir chamadas iguais.
    """
    key = _get_key()
    if not key:
        return []

    results, token = [], None
    for _ in range(2):  # máx 2 páginas = 40 resultados
        if token:
            time.sleep(2)
        params = {
            "query":    query,
            "location": f"{CWB_LAT},{CWB_LNG}",
            "radius":   raio,
            "language": "pt-BR",
            "key":      key,
        }
        if token:
            params["pagetoken"] = token

        r = requests.get(f"{BASE_URL}/place/textsearch/json", params=params, timeout=10)
        data = r.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            break

        results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break

    return results


@st.cache_data(ttl=3600, show_spinner=False)
def place_details(place_id: str) -> dict:
    """Busca telefone + website + horários de um lugar pelo place_id."""
    key = _get_key()
    if not key:
        return {}

    params = {
        "place_id": place_id,
        "fields":   "formatted_phone_number,website,opening_hours",
        "language": "pt-BR",
        "key":      key,
    }
    r = requests.get(f"{BASE_URL}/place/details/json", params=params, timeout=10)
    data = r.json()
    return data.get("result", {})


def buscar_canal_bairro(canal: str, bairro: str, nota_min: float = 0.0) -> list[dict]:
    """
    Busca todos os estabelecimentos de um canal num bairro.
    Retorna lista de dicts padronizados.
    """
    termos = CANAIS.get(canal, [])
    vistos, pontos = set(), []

    for termo in termos:
        query = f"{termo} {bairro} Curitiba"
        resultados = text_search(query)

        for p in resultados:
            pid = p.get("place_id", "")
            if pid in vistos:
                continue
            rating = p.get("rating", 0) or 0
            if rating < nota_min:
                continue
            vistos.add(pid)

            # Filtra pelo endereço para garantir que é do bairro
            addr = (p.get("formatted_address") or p.get("vicinity") or "").lower()
            if bairro.lower() not in addr and "curitiba" not in addr:
                continue

            lat = p["geometry"]["location"]["lat"]
            lng = p["geometry"]["location"]["lng"]

            pontos.append({
                "place_id":  pid,
                "nome":      p.get("name", ""),
                "endereco":  p.get("formatted_address") or p.get("vicinity") or "",
                "bairro":    bairro,
                "regiao":    BAIRRO_REGIAO.get(bairro, ""),
                "canal":     canal,
                "avaliacao": rating,
                "n_aval":    p.get("user_ratings_total", 0) or 0,
                "aberto":    p.get("opening_hours", {}).get("open_now"),
                "lat":       lat,
                "lng":       lng,
                "telefone":  "",
                "website":   "",
            })

    return pontos


def enriquecer_com_detalhes(pontos: list[dict]) -> list[dict]:
    """
    Para cada ponto, busca telefone e website via Place Details.
    Atualiza os campos in-place e retorna a lista.
    """
    key = _get_key()
    if not key:
        return pontos

    for p in pontos:
        det = place_details(p["place_id"])
        p["telefone"] = det.get("formatted_phone_number", "–")
        p["website"]  = det.get("website", "–")
        hrs = det.get("opening_hours", {}).get("weekday_text", [])
        p["horarios"] = hrs

    return pontos
