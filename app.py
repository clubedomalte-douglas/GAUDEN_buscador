"""
app.py — Gauden Comercial · Prospecção Varejo Curitiba
v2 — fundo branco, mapa OSM, sem região, Excel direto
"""
import io
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from places_api import (
    REGIOES, CANAIS, COR_CANAL, ICONE_CANAL,
    buscar_canal_bairro, enriquecer_com_detalhes,
)
from roteirizador import (
    nearest_neighbor, calcular_stats_rota,
    rota_para_gmaps, rota_para_waze,
)

# ── CONFIG ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gauden · Prospecção Varejo",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS — FUNDO BRANCO ───────────────────────────────────────────
st.markdown("""
<style>
/* Fundo branco */
[data-testid="stAppViewContainer"] { background: #ffffff; }
[data-testid="stSidebar"] {
  background: #f8f9fa;
  border-right: 1px solid #e0e0e0;
}
section[data-testid="stSidebarContent"] { background: #f8f9fa; }

/* Texto geral escuro */
html, body, [class*="css"] { color: #1a1a1a; }

/* Métricas */
[data-testid="metric-container"] {
  background: #f0f4ff;
  border: 1px solid #d0d8f0;
  border-radius: 10px;
  padding: 12px 16px;
}
[data-testid="stMetricValue"] { color: #1a56db !important; font-family: monospace; }
[data-testid="stMetricLabel"] { color: #666 !important; font-size: 11px !important; }

/* Cards */
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.card-nome { font-size: 14px; font-weight: 700; color: #111; margin-bottom: 2px; }
.card-sub  { font-size: 11px; color: #888; font-family: monospace; }
.card-tel  { font-size: 12px; color: #1a56db; font-family: monospace; margin-top: 4px; }

/* Badge canal */
.badge {
  display: inline-block; font-size: 10px; font-family: monospace;
  padding: 2px 8px; border-radius: 4px; margin-right: 4px;
}

/* Botão de rota */
.route-btn {
  display: inline-block; background: #1a56db; color: #fff;
  font-weight: 700; font-size: 12px; padding: 6px 14px;
  border-radius: 8px; text-decoration: none;
}

/* Sidebar labels */
.stSelectbox label, .stMultiSelect label,
.stSlider label, .stTextInput label { color: #333 !important; }
</style>
""", unsafe_allow_html=True)


# ── TODOS OS BAIRROS (todas as regiões juntas) ───────────────────
TODOS_BAIRROS = sorted(set(
    b for bairros in REGIOES.values() for b in bairros
))

# ── SESSION STATE ────────────────────────────────────────────────
if "pontos"  not in st.session_state: st.session_state["pontos"]  = []
if "rotas"   not in st.session_state: st.session_state["rotas"]   = []

# ── SIDEBAR ──────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/48/map-marker.png", width=36)
    st.markdown("## Gauden Comercial")
    st.markdown("**Prospecção Varejo · Curitiba**")
    st.divider()

    chave_manual = st.text_input(
        "🔑 Chave Google Maps API",
        type="password",
        placeholder="AIza...",
    )
    if chave_manual:
        st.session_state["api_key_override"] = chave_manual

    st.divider()
    st.markdown("### 🔍 Filtros")

    # SÓ BAIRROS — sem região
    bairros_sel = st.multiselect(
        "📍 Bairros",
        options=TODOS_BAIRROS,
        default=["Batel", "Água Verde"],
        help="Selecione os bairros que deseja prospectar",
    )

    canais_sel = st.multiselect(
        "🏪 Canais",
        options=list(CANAIS.keys()),
        default=list(CANAIS.keys())[:2],
    )

    nota_min = st.slider("⭐ Avaliação mínima", 0.0, 5.0, 3.5, 0.5)
    max_por_rota = st.slider("🚗 Máx. pontos por rota", 5, 20, 15)

    buscar_detalhes = st.toggle(
        "📞 Buscar telefone e site",
        value=False,
        help="Mais lento — faz chamada extra à API por cada estabelecimento",
    )

    st.divider()
    btn_buscar  = st.button("🔍 Buscar estabelecimentos", type="primary", use_container_width=True)
    btn_roteiro = st.button("🚗 Gerar roteiro", use_container_width=True)


# ── OVERRIDE CHAVE ───────────────────────────────────────────────
if "api_key_override" in st.session_state:
    import places_api
    places_api._get_key = lambda: st.session_state["api_key_override"]


# ── BUSCA ────────────────────────────────────────────────────────
if btn_buscar:
    if not bairros_sel:
        st.warning("Selecione pelo menos um bairro.")
    elif not canais_sel:
        st.warning("Selecione pelo menos um canal.")
    else:
        pontos, total, step = [], len(bairros_sel) * len(canais_sel), 0
        prog = st.progress(0, text="Iniciando busca...")

        for bairro in bairros_sel:
            for canal in canais_sel:
                step += 1
                prog.progress(step / total, text=f"🔍 {canal[:20]} em {bairro}...")
                pontos.extend(buscar_canal_bairro(canal, bairro, nota_min))

        vistos, pontos_unicos = set(), []
        for p in pontos:
            if p["place_id"] not in vistos:
                vistos.add(p["place_id"])
                pontos_unicos.append(p)

        if buscar_detalhes and pontos_unicos:
            prog.progress(0.95, text=f"📞 Buscando telefones ({len(pontos_unicos)} locais)...")
            pontos_unicos = enriquecer_com_detalhes(pontos_unicos)

        prog.empty()
        st.session_state["pontos"] = pontos_unicos
        st.session_state["rotas"]  = []
        st.success(f"✅ {len(pontos_unicos)} estabelecimentos encontrados!")


# ── ROTEIRIZAÇÃO ─────────────────────────────────────────────────
if btn_roteiro:
    pontos = st.session_state.get("pontos", [])
    if not pontos:
        st.warning("Faça a busca primeiro.")
    else:
        rotas = nearest_neighbor(pontos, max_por_rota)
        st.session_state["rotas"] = rotas
        st.success(f"✅ {len(rotas)} rota(s) gerada(s) com até {max_por_rota} pontos cada!")


# ── DADOS ────────────────────────────────────────────────────────
pontos = st.session_state.get("pontos", [])
rotas  = st.session_state.get("rotas",  [])


# ── HEADER PRINCIPAL ─────────────────────────────────────────────
st.markdown("# 🗺️ Gauden Comercial — Prospecção Varejo")
bairros_txt = ", ".join(bairros_sel) if bairros_sel else "Nenhum bairro selecionado"
st.markdown(f"📍 **{bairros_txt}**")

# Métricas
if pontos:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(pontos))
    c2.metric("Bairros", len(set(p["bairro"] for p in pontos)))
    c3.metric("Canais",  len(set(p["canal"]  for p in pontos)))
    c4.metric("Rotas",   len(rotas) if rotas else "–")

    # ── BOTÃO EXCEL DIRETO (destaque) ──
    st.markdown("---")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_est = pd.DataFrame([{
            "Nome":      p["nome"],
            "Bairro":    p["bairro"],
            "Canal":     p["canal"],
            "Endereço":  p["endereco"],
            "Avaliação": p["avaliacao"],
            "Nº Aval.":  p["n_aval"],
            "Telefone":  p.get("telefone", ""),
            "Site/Email": p.get("website", ""),
        } for p in pontos])
        df_est.to_excel(writer, index=False, sheet_name="Estabelecimentos")

        if rotas:
            rotas_rows = []
            for i, rota in enumerate(rotas):
                for j, p in enumerate(rota):
                    rotas_rows.append({
                        "Rota": i+1, "Ordem": j+1,
                        "Nome": p["nome"], "Bairro": p["bairro"],
                        "Canal": p["canal"], "Endereço": p["endereco"],
                        "Telefone": p.get("telefone",""),
                        "Avaliação": p["avaliacao"],
                    })
            pd.DataFrame(rotas_rows).to_excel(writer, index=False, sheet_name="Roteiro")

    nome_arquivo = f"gauden_{'_'.join(bairros_sel[:2]).lower().replace(' ','_')}.xlsx"
    st.download_button(
        label="📥 Baixar Excel com todos os dados",
        data=buf.getvalue(),
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
    st.markdown("---")

# ── ABAS ─────────────────────────────────────────────────────────
aba_mapa, aba_lista, aba_rotas = st.tabs(["🗺️ Mapa", "📋 Lista", "🚗 Rotas"])


# ════════════════════════════════════════════════════════════════
# ABA MAPA — OpenStreetMap sem chave, sem marca d'água
# ════════════════════════════════════════════════════════════════
with aba_mapa:
    if not pontos:
        st.info("👈 Configure os filtros na barra lateral e clique em **Buscar**.")
    else:
        # Centro automático nos pontos
        lat_c = sum(p["lat"] for p in pontos) / len(pontos)
        lng_c = sum(p["lng"] for p in pontos) / len(pontos)

        m = folium.Map(
            location=[lat_c, lng_c],
            zoom_start=14,
            tiles="OpenStreetMap",   # gratuito, sem chave, sem marca d'água
        )

        # Pins por canal
        for p in pontos:
            cor = COR_CANAL.get(p["canal"], "#1a56db")
            ico = ICONE_CANAL.get(p["canal"], "📍")
            tel = p.get("telefone","")
            site = p.get("website","")

            popup_html = f"""
            <div style="font-family:sans-serif;font-size:12px;min-width:200px">
              <b style="font-size:13px">{p['nome']}</b><br>
              <span style="color:#555">{p['canal']}</span><br>
              <span>📍 {p['bairro']}</span><br>
              <span>⭐ {p['avaliacao']} ({p['n_aval']:,} aval.)</span>
              {f"<br>📞 <b>{tel}</b>" if tel and tel!='–' else ''}
              {f"<br>🌐 <a href='{site}' target='_blank'>{site[:35]}</a>" if site and site!='–' else ''}
              <br><br>
              <a href="https://www.google.com/maps/search/{p['nome']} {p['endereco']}"
                 target="_blank"
                 style="background:#1a56db;color:#fff;padding:4px 10px;border-radius:4px;
                        text-decoration:none;font-weight:700;font-size:11px">
                🗺 Abrir no Maps
              </a>
            </div>
            """

            folium.CircleMarker(
                location=[p["lat"], p["lng"]],
                radius=9,
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.85,
                weight=2,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{ico} {p['nome']} · {p['bairro']}",
            ).add_to(m)

        # Rotas
        if rotas:
            cores_rota = ["#e63946","#2196f3","#ff9800","#4caf50","#9c27b0"]
            for i, rota in enumerate(rotas):
                cor_r = cores_rota[i % len(cores_rota)]
                coords = [(p["lat"], p["lng"]) for p in rota]
                folium.PolyLine(coords, color=cor_r, weight=3, opacity=0.7,
                    tooltip=f"Rota {i+1} · {len(rota)} paradas").add_to(m)
                for j, p in enumerate(rota):
                    folium.Marker(
                        location=[p["lat"], p["lng"]],
                        icon=folium.DivIcon(
                            html=f'<div style="background:{cor_r};color:#fff;font-weight:700;'
                                 f'font-size:11px;width:22px;height:22px;border-radius:50%;'
                                 f'display:flex;align-items:center;justify-content:center;'
                                 f'border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)">'
                                 f'{j+1}</div>',
                            icon_size=(22,22), icon_anchor=(11,11),
                        ),
                        tooltip=f"#{j+1} {p['nome']}",
                    ).add_to(m)

        st_folium(m, use_container_width=True, height=520)


# ════════════════════════════════════════════════════════════════
# ABA LISTA
# ════════════════════════════════════════════════════════════════
with aba_lista:
    if not pontos:
        st.info("Faça a busca primeiro.")
    else:
        col_f1, col_f2, col_f3 = st.columns([2,2,1])
        with col_f1:
            filtro_canal  = st.selectbox("Canal",  ["Todos"]+list(set(p["canal"]  for p in pontos)), key="lfc")
        with col_f2:
            filtro_bairro = st.selectbox("Bairro", ["Todos"]+sorted(set(p["bairro"] for p in pontos)), key="lfb")
        with col_f3:
            ordenar = st.selectbox("Ordenar", ["⭐ Avaliação","Nome","Bairro"], key="lfo")

        lista = pontos
        if filtro_canal  != "Todos": lista = [p for p in lista if p["canal"]  == filtro_canal]
        if filtro_bairro != "Todos": lista = [p for p in lista if p["bairro"] == filtro_bairro]
        if ordenar == "⭐ Avaliação": lista = sorted(lista, key=lambda p: p["avaliacao"], reverse=True)
        elif ordenar == "Nome":       lista = sorted(lista, key=lambda p: p["nome"])
        else:                         lista = sorted(lista, key=lambda p: p["bairro"])

        st.caption(f"{len(lista)} estabelecimentos")
        cols = st.columns(2)
        for i, p in enumerate(lista):
            cor = COR_CANAL.get(p["canal"], "#888")
            ico = ICONE_CANAL.get(p["canal"], "📍")
            tel  = p.get("telefone","")
            site = p.get("website","")
            aberto_txt = "🟢 Aberto" if p.get("aberto") is True else ("🔴 Fechado" if p.get("aberto") is False else "")
            with cols[i % 2]:
                st.markdown(f"""
                <div class="card">
                  <div class="card-nome">{ico} {p['nome']}</div>
                  <div class="card-sub">
                    <span class="badge" style="background:{cor}22;color:{cor};border:.5px solid {cor}55">
                      {p['canal'].split('—')[0].strip()}
                    </span>
                    📍 {p['bairro']} · ⭐ {p['avaliacao']} ({p['n_aval']:,}) {aberto_txt}
                  </div>
                  <div class="card-sub" style="margin-top:3px;color:#999">{p['endereco'][:65]}</div>
                  {f'<div class="card-tel">📞 {tel}</div>' if tel and tel!="–" else ''}
                  {f'<div class="card-sub"><a href="{site}" target="_blank" style="color:#1a56db">🌐 {site[:40]}</a></div>' if site and site!="–" else ''}
                </div>
                """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# ABA ROTAS
# ════════════════════════════════════════════════════════════════
with aba_rotas:
    if not rotas:
        st.info("Clique em **🚗 Gerar roteiro** na barra lateral para criar as rotas." if pontos else "Faça a busca primeiro.")
    else:
        st.markdown(f"### {len(rotas)} rota(s) · até {max_por_rota} paradas cada")
        cores_rota = ["#e63946","#2196f3","#ff9800","#4caf50","#9c27b0"]

        for i, rota in enumerate(rotas):
            stats = calcular_stats_rota(rota)
            cor_r = cores_rota[i % len(cores_rota)]
            url_gmaps = rota_para_gmaps(rota)

            with st.expander(
                f"🚗 Rota {i+1} · {stats['n_pontos']} paradas · ~{stats['dist_km']} km · {stats['tempo_est']}",
                expanded=(i == 0),
            ):
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Paradas",      stats["n_pontos"])
                rc2.metric("Distância",    f"{stats['dist_km']} km")
                rc3.metric("Tempo est.",   stats["tempo_est"])
                st.caption("⏱ 25 km/h médio + 10 min por visita")
                st.markdown(f"**Bairros:** {', '.join(stats['bairros'])}")

                st.markdown(
                    f'<a href="{url_gmaps}" target="_blank" class="route-btn">'
                    f'🗺 Abrir rota no Google Maps</a>',
                    unsafe_allow_html=True,
                )
                st.markdown("")

                for j, p in enumerate(rota):
                    ico = ICONE_CANAL.get(p["canal"],"📍")
                    tel = p.get("telefone","")
                    url_waze = f"https://waze.com/ul?ll={p['lat']},{p['lng']}&navigate=yes"
                    col_n, col_info, col_nav = st.columns([1,7,2])
                    with col_n:
                        st.markdown(
                            f'<div style="background:{cor_r};color:#fff;font-weight:700;'
                            f'font-size:12px;width:26px;height:26px;border-radius:50%;'
                            f'display:flex;align-items:center;justify-content:center;'
                            f'margin-top:4px">{j+1}</div>',
                            unsafe_allow_html=True,
                        )
                    with col_info:
                        st.markdown(
                            f'<div style="font-size:13px;font-weight:600;color:#111">{ico} {p["nome"]}</div>'
                            f'<div style="font-size:11px;color:#888;font-family:monospace">'
                            f'📍 {p["bairro"]} · ⭐ {p["avaliacao"]}'
                            f'{f" · 📞 {tel}" if tel and tel!="–" else ""}</div>',
                            unsafe_allow_html=True,
                        )
                    with col_nav:
                        st.markdown(
                            f'<a href="{url_waze}" target="_blank" '
                            f'style="font-size:11px;color:#1a56db;text-decoration:none">🧭 Waze</a>',
                            unsafe_allow_html=True,
                        )
                    if j < len(rota)-1:
                        st.divider()
