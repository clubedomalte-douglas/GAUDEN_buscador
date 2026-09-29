"""
roteirizador.py — Geração de rotas otimizadas por região
Gauden Comercial · App de Prospecção Varejo Curitiba

Algoritmo: Nearest Neighbor Heuristic (sem API externa)
Cobre até 20 pontos por rota. Se houver mais, divide em sub-rotas.
"""
import math
import pandas as pd


def _dist(a: dict, b: dict) -> float:
    """Distância euclidiana aproximada entre dois pontos lat/lng."""
    dlat = a["lat"] - b["lat"]
    dlng = a["lng"] - b["lng"]
    return math.sqrt(dlat**2 + dlng**2)


def nearest_neighbor(pontos: list[dict], max_por_rota: int = 20) -> list[list[dict]]:
    """
    Divide os pontos em rotas de até max_por_rota estabelecimentos,
    ordenadas pelo algoritmo do vizinho mais próximo.
    Retorna lista de rotas (cada rota = lista de pontos).
    """
    if not pontos:
        return []

    pendentes = list(pontos)
    rotas = []

    while pendentes:
        rota = []
        # Começa pelo ponto mais ao norte (lat mais negativa = mais ao norte em Curitiba)
        atual = min(pendentes, key=lambda p: p["lat"])
        pendentes.remove(atual)
        rota.append(atual)

        while pendentes and len(rota) < max_por_rota:
            # Próximo mais próximo do atual
            proximo = min(pendentes, key=lambda p: _dist(atual, p))
            pendentes.remove(proximo)
            rota.append(proximo)
            atual = proximo

        rotas.append(rota)

    return rotas


def calcular_stats_rota(rota: list[dict]) -> dict:
    """Calcula estatísticas de uma rota."""
    if not rota:
        return {}

    dist_total = 0.0
    for i in range(len(rota) - 1):
        # Converte graus para km aproximado (1° lat ≈ 111 km)
        dlat = (rota[i+1]["lat"] - rota[i]["lat"]) * 111
        dlng = (rota[i+1]["lng"] - rota[i]["lng"]) * 111 * math.cos(math.radians(-25.44))
        dist_total += math.sqrt(dlat**2 + dlng**2)

    canais = pd.Series([p["canal"] for p in rota]).value_counts().to_dict()

    return {
        "n_pontos":   len(rota),
        "dist_km":    round(dist_total, 1),
        "tempo_est":  f"{int(dist_total / 25 * 60 + len(rota) * 10)} min",  # 25 km/h + 10 min por visita
        "canais":     canais,
        "bairros":    list(set(p["bairro"] for p in rota)),
    }


def rota_para_gmaps(rota: list[dict]) -> str:
    """
    Gera URL do Google Maps com waypoints para navegação.
    Abre direto no app do Maps no celular.
    """
    if not rota:
        return ""

    base = "https://www.google.com/maps/dir/"
    waypoints = "/".join(
        f"{p['lat']},{p['lng']}" for p in rota
    )
    return base + waypoints


def rota_para_waze(rota: list[dict]) -> list[str]:
    """
    Gera URLs do Waze para cada parada (Waze não suporta múltiplos waypoints na URL).
    """
    return [
        f"https://waze.com/ul?ll={p['lat']},{p['lng']}&navigate=yes"
        for p in rota
    ]
