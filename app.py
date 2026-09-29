"""
app.py — Gauden Comercial · Prospecção Varejo Curitiba
v3 — layout limpo, tema claro, mapa OSM
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
    nearest_neighbor, calcular_stats_rota, rota_para_gmaps,
)

# ── CONFIG ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gauden · Prospecção Varejo",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── SESSION STATE ────────────────────────────────────────────────
if "pontos" not in st.session_state: st.session_state["pontos"] = []
if "rotas"  not in st.session_state: st.session_state["rotas"]  = []

# ── TODOS OS BAIRROS ─────────────────────────────────────────────
TODOS_BAIRROS = sorted(set(b for bs in REGIOES.values() for b in bs))

# ════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🗺️ Gauden Comercial")
    st.caption("Prospecção Varejo · Curitiba")
    st.divider()

    # Chave API
    chave = st.text_input("🔑 Chave Google Maps API", type="password", placeholder="AIza...")
    if chave:
        st.session_state["api_key_override"] = chave
    if "api_key_override" in st.session_state:
        import places_api
        places_api._get_key = lambda: st.session_state["api_key_override"]

    st.divider()

    # Bairros
    bairros_sel = st.multiselect(
        "📍 Bairros",
        options=TODOS_BAIRROS,
        default=["Batel", "Água Verde"],
    )

    # Canais
    canais_sel = st.multiselect(
        "🏪 Canais",
        options=list(CANAIS.keys()),
        default=list(CANAIS.keys())[:2],
    )

    nota_min     = st.slider("⭐ Avaliação mínima", 0.0, 5.0, 3.5, 0.5)
    max_rota     = st.slider("🚗 Pontos por rota", 5, 20, 15)
    com_detalhes = st.toggle("📞 Buscar telefone e site", value=False)

    st.divider()
    btn_buscar  = st.button("🔍 Buscar", type="primary", use_container_width=True)
    btn_roteiro = st.button("🚗 Gerar roteiro", use_container_width=True)


# ════════════════════════════════════════════════════════════════
# BUSCA
# ════════════════════════════════════════════════════════════════
if btn_buscar:
    if not bairros_sel or not canais_sel:
        st.warning("Selecione bairros e canais.")
    else:
        pontos, total, step = [], len(bairros_sel) * len(canais_sel), 0
        prog = st.progress(0, text="Buscando...")
        for bairro in bairros_sel:
            for canal in canais_sel:
                step += 1
                prog.progress(step / total, text=f"🔍 {bairro} — {canal[:25]}...")
                pontos.extend(buscar_canal_bairro(canal, bairro, nota_min))

        vistos, unicos = set(), []
        for p in pontos:
            if p["place_id"] not in vistos:
                vistos.add(p["place_id"])
                unicos.append(p)

        if com_detalhes and unicos:
            prog.progress(0.95, text="📞 Buscando telefones...")
            unicos = enriquecer_com_detalhes(unicos)

        prog.empty()
        st.session_state["pontos"] = unicos
        st.session_state["rotas"]  = []
        st.success(f"✅ {len(unicos)} estabelecimentos encontrados!")

if btn_roteiro:
    pontos = st.session_state.get("pontos", [])
    if not pontos:
        st.warning("Faça a busca primeiro.")
    else:
        rotas = nearest_neighbor(pontos, max_rota)
        st.session_state["rotas"] = rotas
        st.success(f"✅ {len(rotas)} rota(s) gerada(s)!")


# ════════════════════════════════════════════════════════════════
# CONTEÚDO PRINCIPAL
# ════════════════════════════════════════════════════════════════
pontos = st.session_state.get("pontos", [])
rotas  = st.session_state.get("rotas",  [])

st.title("🗺️ Gauden Comercial — Prospecção Varejo")

# ── Métricas + Botão Excel ───────────────────────────────────────
if pontos:
    col1, col2, col3, col4, col5 = st.columns([1,1,1,1,2])
    col1.metric("Total",    len(pontos))
    col2.metric("Bairros",  len(set(p["bairro"] for p in pontos)))
    col3.metric("Canais",   len(set(p["canal"]  for p in pontos)))
    col4.metric("Rotas",    len(rotas) if rotas else "–")

    # Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Nome":       p["nome"],
            "Bairro":     p["bairro"],
            "Canal":      p["canal"],
            "Endereço":   p["endereco"],
            "Avaliação":  p["avaliacao"],
            "Nº Aval.":   p["n_aval"],
            "Telefone":   p.get("telefone",""),
            "Site/Email": p.get("website",""),
        } for p in pontos]).to_excel(writer, index=False, sheet_name="Estabelecimentos")
        if rotas:
            pd.DataFrame([{
                "Rota": i+1, "Ordem": j+1,
                "Nome": p["nome"], "Bairro": p["bairro"],
                "Endereço": p["endereco"], "Telefone": p.get("telefone",""),
            } for i,rota in enumerate(rotas) for j,p in enumerate(rota)
            ]).to_excel(writer, index=False, sheet_name="Roteiro")

    with col5:
        st.download_button(
            "📥 Baixar Excel",
            data=buf.getvalue(),
            file_name="gauden_prospeccao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )

    st.divider()

# ── Abas ──────────────────────────────────────────────────────────
aba_mapa, aba_lista, aba_rotas = st.tabs(["🗺️ Mapa", "📋 Lista", "🚗 Rotas"])


# ════════════════════════════════════════════════════════════════
# ABA MAPA
# ════════════════════════════════════════════════════════════════
with aba_mapa:
    if not pontos:
        st.info("👈 Selecione bairros e canais na barra lateral e clique em **Buscar**.")
    else:
        lat_c = sum(p["lat"] for p in pontos) / len(pontos)
        lng_c = sum(p["lng"] for p in pontos) / len(pontos)

        m = folium.Map(location=[lat_c, lng_c], zoom_start=14, tiles="OpenStreetMap")

        for p in pontos:
            cor = COR_CANAL.get(p["canal"], "#1a56db")
            ico = ICONE_CANAL.get(p["canal"], "📍")
            tel  = p.get("telefone","")
            site = p.get("website","")
            popup = f"""
            <div style="font-family:sans-serif;font-size:12px;min-width:200px">
              <b>{p['nome']}</b><br>
              <span style="color:#555">{p['canal']}</span><br>
              📍 {p['bairro']} · ⭐ {p['avaliacao']} ({p['n_aval']:,})<br>
              {f"📞 <b>{tel}</b><br>" if tel and tel!='–' else ''}
              {f"🌐 <a href='{site}' target='_blank'>{site[:35]}</a><br>" if site and site!='–' else ''}
              <br><a href="https://www.google.com/maps/search/{p['nome']} {p['endereco']}"
                 target="_blank"
                 style="background:#1a56db;color:#fff;padding:3px 10px;border-radius:4px;
                        text-decoration:none;font-weight:700;font-size:11px">
                🗺 Maps</a>
            </div>"""
            folium.CircleMarker(
                location=[p["lat"], p["lng"]],
                radius=9, color=cor, fill=True, fill_color=cor,
                fill_opacity=0.85, weight=2,
                popup=folium.Popup(popup, max_width=260),
                tooltip=f"{ico} {p['nome']} · {p['bairro']}",
            ).add_to(m)

        if rotas:
            CORES_R = ["#e63946","#2196f3","#ff9800","#4caf50","#9c27b0"]
            for i, rota in enumerate(rotas):
                cr = CORES_R[i % len(CORES_R)]
                folium.PolyLine(
                    [(p["lat"],p["lng"]) for p in rota],
                    color=cr, weight=3, opacity=0.7,
                    tooltip=f"Rota {i+1}"
                ).add_to(m)
                for j, p in enumerate(rota):
                    folium.Marker(
                        [p["lat"],p["lng"]],
                        icon=folium.DivIcon(
                            html=f'<div style="background:{cr};color:#fff;font-weight:700;'
                                 f'font-size:11px;width:22px;height:22px;border-radius:50%;'
                                 f'display:flex;align-items:center;justify-content:center;'
                                 f'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3)">{j+1}</div>',
                            icon_size=(22,22), icon_anchor=(11,11),
                        ), tooltip=f"#{j+1} {p['nome']}",
                    ).add_to(m)

        st_folium(m, use_container_width=True, height=520)


# ════════════════════════════════════════════════════════════════
# ABA LISTA
# ════════════════════════════════════════════════════════════════
with aba_lista:
    if not pontos:
        st.info("Faça a busca primeiro.")
    else:
        c1, c2, c3 = st.columns([2,2,1])
        fc = c1.selectbox("Canal",  ["Todos"]+list(set(p["canal"]  for p in pontos)))
        fb = c2.selectbox("Bairro", ["Todos"]+sorted(set(p["bairro"] for p in pontos)))
        fo = c3.selectbox("Ordenar",["⭐ Nota","Nome","Bairro"])

        lista = [p for p in pontos
                 if (fc=="Todos" or p["canal"]==fc)
                 and (fb=="Todos" or p["bairro"]==fb)]
        if fo=="⭐ Nota":   lista = sorted(lista, key=lambda p:-p["avaliacao"])
        elif fo=="Nome":   lista = sorted(lista, key=lambda p:p["nome"])
        else:              lista = sorted(lista, key=lambda p:p["bairro"])

        st.caption(f"{len(lista)} estabelecimentos")

        for p in lista:
            cor = COR_CANAL.get(p["canal"],"#888")
            ico = ICONE_CANAL.get(p["canal"],"📍")
            tel  = p.get("telefone","")
            site = p.get("website","")
            with st.container(border=True):
                cols = st.columns([4,1])
                with cols[0]:
                    st.markdown(f"**{ico} {p['nome']}**")
                    st.caption(f"📍 {p['bairro']}  ·  {p['canal'].split('—')[-1].strip()}  ·  ⭐ {p['avaliacao']} ({p['n_aval']:,})")
                    st.caption(p['endereco'])
                    if tel and tel!="–": st.markdown(f"📞 `{tel}`")
                    if site and site!="–": st.markdown(f"🌐 [{site[:45]}]({site})")
                with cols[1]:
                    st.markdown(f"[🗺 Maps](https://www.google.com/maps/search/{p['nome']} {p['endereco']})")


# ════════════════════════════════════════════════════════════════
# ABA ROTAS
# ════════════════════════════════════════════════════════════════
with aba_rotas:
    if not rotas:
        st.info("Clique em **🚗 Gerar roteiro** na barra lateral." if pontos else "Faça a busca primeiro.")
    else:
        CORES_R = ["#e63946","#2196f3","#ff9800","#4caf50","#9c27b0"]
        st.markdown(f"**{len(rotas)} rota(s) gerada(s)** · até {max_rota} paradas cada")

        for i, rota in enumerate(rotas):
            stats = calcular_stats_rota(rota)
            cr    = CORES_R[i % len(CORES_R)]
            with st.expander(
                f"🚗 Rota {i+1}  ·  {stats['n_pontos']} paradas  ·  ~{stats['dist_km']} km  ·  {stats['tempo_est']}",
                expanded=(i==0)
            ):
                c1,c2,c3 = st.columns(3)
                c1.metric("Paradas",   stats["n_pontos"])
                c2.metric("Distância", f"{stats['dist_km']} km")
                c3.metric("Tempo est.",stats["tempo_est"])
                st.caption("⏱ 25 km/h médio + 10 min por visita")
                st.markdown(f"**Bairros:** {', '.join(stats['bairros'])}")
                url = rota_para_gmaps(rota)
                st.link_button("🗺 Abrir rota no Google Maps", url, use_container_width=True)
                st.divider()

                for j, p in enumerate(rota):
                    ico = ICONE_CANAL.get(p["canal"],"📍")
                    tel = p.get("telefone","")
                    waze = f"https://waze.com/ul?ll={p['lat']},{p['lng']}&navigate=yes"
                    ca, cb, cc = st.columns([1,7,2])
                    ca.markdown(
                        f'<div style="background:{cr};color:#fff;font-weight:700;font-size:12px;'
                        f'width:26px;height:26px;border-radius:50%;display:flex;align-items:center;'
                        f'justify-content:center;margin-top:6px">{j+1}</div>',
                        unsafe_allow_html=True
                    )
                    cb.markdown(f"**{ico} {p['nome']}**")
                    cb.caption(f"📍 {p['bairro']} · ⭐ {p['avaliacao']}" + (f" · 📞 {tel}" if tel and tel!="–" else ""))
                    cc.markdown(f"[🧭 Waze]({waze})")
                    if j < len(rota)-1:
                        st.divider()
