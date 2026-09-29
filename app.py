"""
app.py — Gauden Comercial · Prospecção Varejo Curitiba
Streamlit Cloud · Places API + Roteirização
"""
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

# ── CSS CUSTOMIZADO ──────────────────────────────────────────────
st.markdown("""
<style>
/* Fundo geral */
[data-testid="stAppViewContainer"] { background: #0d0d0d; }
[data-testid="stSidebar"] { background: #111; border-right: 1px solid #1e1e1e; }

/* Métrica */
[data-testid="metric-container"] {
  background: #161616; border: .5px solid #2a2a2a;
  border-radius: 10px; padding: 12px 16px;
}
[data-testid="stMetricValue"] { color: #c8f06e !important; font-family: monospace; }
[data-testid="stMetricLabel"] { color: #555 !important; font-size: 11px !important; }

/* Cards de estabelecimento */
.card {
  background: #161616; border: .5px solid #2a2a2a;
  border-radius: 10px; padding: 12px 14px; margin-bottom: 8px;
}
.card-nome { font-size: 14px; font-weight: 700; color: #f0ede8; margin-bottom: 2px; }
.card-sub  { font-size: 11px; color: #555; font-family: monospace; }
.card-tel  { font-size: 12px; color: #c8f06e; font-family: monospace; margin-top: 4px; }

/* Badge canal */
.badge {
  display: inline-block; font-size: 10px; font-family: monospace;
  padding: 2px 8px; border-radius: 4px; margin-right: 4px;
}

/* Botão de rota */
.route-btn {
  display: inline-block; background: #c8f06e; color: #0d0d0d;
  font-weight: 700; font-size: 12px; padding: 6px 14px;
  border-radius: 8px; text-decoration: none;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗺️ Gauden Comercial")
    st.markdown("**Prospecção Varejo · Curitiba**")
    st.divider()

    # Chave API (opcional — pode estar no secrets)
    chave_manual = st.text_input(
        "🔑 Chave Google Maps API",
        type="password",
        help="Cole aqui ou configure em st.secrets['GOOGLE_MAPS_KEY']",
        placeholder="AIza...",
    )
    if chave_manual:
        st.session_state["api_key_override"] = chave_manual

    st.divider()

    # Filtros
    st.markdown("### Filtros")

    regiao_sel = st.selectbox(
        "📍 Região",
        options=list(REGIOES.keys()),
    )

    bairros_disponiveis = REGIOES[regiao_sel]
    bairros_sel = st.multiselect(
        "🏘️ Bairros",
        options=bairros_disponiveis,
        default=bairros_disponiveis[:3],
        help="Selecione até 5 bairros para consulta rápida",
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
        help="Faz chamada extra à Place Details API — mais lento mas traz telefone e site",
    )

    st.divider()
    btn_buscar = st.button("🔍 Buscar estabelecimentos", type="primary", use_container_width=True)
    btn_roteiro = st.button("🚗 Gerar roteiro", use_container_width=True)


# ── SESSION STATE ────────────────────────────────────────────────
if "pontos" not in st.session_state:
    st.session_state["pontos"] = []
if "rotas" not in st.session_state:
    st.session_state["rotas"] = []
if "aba" not in st.session_state:
    st.session_state["aba"] = "mapa"


# ── OVERRIDE CHAVE ───────────────────────────────────────────────
if "api_key_override" in st.session_state:
    import places_api
    # Injeta chave no módulo sem precisar do secrets
    _orig = places_api._get_key
    places_api._get_key = lambda: st.session_state["api_key_override"]


# ── BUSCA ────────────────────────────────────────────────────────
if btn_buscar:
    if not bairros_sel:
        st.warning("Selecione pelo menos um bairro.")
    elif not canais_sel:
        st.warning("Selecione pelo menos um canal.")
    else:
        pontos = []
        total = len(bairros_sel) * len(canais_sel)
        prog = st.progress(0, text="Iniciando busca...")
        step = 0

        for bairro in bairros_sel:
            for canal in canais_sel:
                step += 1
                prog.progress(step / total, text=f"🔍 {canal[:20]} em {bairro}...")
                res = buscar_canal_bairro(canal, bairro, nota_min)
                pontos.extend(res)

        # Remove duplicatas por place_id
        vistos = set()
        pontos_unicos = []
        for p in pontos:
            if p["place_id"] not in vistos:
                vistos.add(p["place_id"])
                pontos_unicos.append(p)

        if buscar_detalhes and pontos_unicos:
            prog.progress(0.95, text=f"📞 Buscando telefones ({len(pontos_unicos)} locais)...")
            pontos_unicos = enriquecer_com_detalhes(pontos_unicos)

        prog.empty()
        st.session_state["pontos"] = pontos_unicos
        st.session_state["rotas"] = []
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


# ── CONTEÚDO PRINCIPAL ───────────────────────────────────────────
pontos = st.session_state.get("pontos", [])
rotas  = st.session_state.get("rotas", [])

# Header
st.markdown("# 🗺️ Gauden Comercial — Prospecção Varejo")
st.markdown(f"**{regiao_sel}** · {', '.join(bairros_sel) if bairros_sel else 'Nenhum bairro selecionado'}")

# Métricas
if pontos:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(pontos))
    c2.metric("Bairros", len(set(p["bairro"] for p in pontos)))
    c3.metric("Canais", len(set(p["canal"] for p in pontos)))
    c4.metric("Rotas", len(rotas) if rotas else "–")
    st.divider()

# Abas
aba_mapa, aba_lista, aba_rotas, aba_export = st.tabs([
    "🗺️ Mapa", "📋 Lista", "🚗 Rotas", "📥 Exportar"
])


# ════════════════════════════════════════════════════════════════
# ABA MAPA
# ════════════════════════════════════════════════════════════════
with aba_mapa:
    if not pontos:
        st.info("👈 Configure os filtros na barra lateral e clique em **Buscar**.")
    else:
        # Cria mapa Folium
        m = folium.Map(
            location=[-25.4490, -49.2890],
            zoom_start=13,
            tiles="CartoDB dark_matter",
        )

        # Adiciona pins
        for p in pontos:
            cor = COR_CANAL.get(p["canal"], "#ffffff")
            ico = ICONE_CANAL.get(p["canal"], "📍")

            popup_html = f"""
            <div style="font-family:monospace;font-size:12px;min-width:200px">
              <b style="font-size:14px">{p['nome']}</b><br>
              <span style="color:#888">{p['canal']}</span><br>
              <span style="color:#aaa">📍 {p['bairro']}</span><br>
              <span style="color:#aaa">⭐ {p['avaliacao']}</span>
              {f"<br>📞 {p['telefone']}" if p.get('telefone') and p['telefone'] != '–' else ''}
              {f"<br>🌐 <a href='{p['website']}' target='_blank'>Site</a>" if p.get('website') and p['website'] != '–' else ''}
              <br><br>
              <a href="https://www.google.com/maps/search/{p['nome']} {p['endereco']}"
                 target="_blank" style="background:#c8f06e;color:#000;padding:3px 8px;border-radius:4px;text-decoration:none;font-weight:700">
                🗺 Maps
              </a>
            </div>
            """

            folium.CircleMarker(
                location=[p["lat"], p["lng"]],
                radius=8,
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.85,
                weight=2,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{ico} {p['nome']} · {p['bairro']}",
            ).add_to(m)

        # Se tem rotas, desenha as linhas
        if rotas:
            cores_rota = ["#c8f06e", "#6eaaf0", "#f06eaa", "#f0b06e", "#e890ff"]
            for i, rota in enumerate(rotas):
                cor_r = cores_rota[i % len(cores_rota)]
                coords = [(p["lat"], p["lng"]) for p in rota]
                folium.PolyLine(
                    coords, color=cor_r, weight=2.5, opacity=0.7,
                    tooltip=f"Rota {i+1} · {len(rota)} paradas",
                ).add_to(m)
                # Numeração das paradas
                for j, p in enumerate(rota):
                    folium.Marker(
                        location=[p["lat"], p["lng"]],
                        icon=folium.DivIcon(
                            html=f'<div style="background:{cor_r};color:#000;font-family:monospace;'
                                 f'font-weight:700;font-size:11px;width:20px;height:20px;'
                                 f'border-radius:50%;display:flex;align-items:center;'
                                 f'justify-content:center;border:2px solid #000">{j+1}</div>',
                            icon_size=(20, 20), icon_anchor=(10, 10),
                        ),
                        tooltip=f"#{j+1} {p['nome']}",
                    ).add_to(m)

        st_folium(m, use_container_width=True, height=560)


# ════════════════════════════════════════════════════════════════
# ABA LISTA
# ════════════════════════════════════════════════════════════════
with aba_lista:
    if not pontos:
        st.info("Faça a busca primeiro.")
    else:
        # Filtros rápidos na lista
        col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
        with col_f1:
            filtro_canal = st.selectbox(
                "Canal", ["Todos"] + list(set(p["canal"] for p in pontos)), key="lf_canal"
            )
        with col_f2:
            filtro_bairro = st.selectbox(
                "Bairro", ["Todos"] + sorted(set(p["bairro"] for p in pontos)), key="lf_bairro"
            )
        with col_f3:
            ordenar = st.selectbox("Ordenar", ["⭐ Avaliação", "Nome", "Bairro"], key="lf_ord")

        # Aplica filtros
        lista = pontos
        if filtro_canal != "Todos":
            lista = [p for p in lista if p["canal"] == filtro_canal]
        if filtro_bairro != "Todos":
            lista = [p for p in lista if p["bairro"] == filtro_bairro]
        if ordenar == "⭐ Avaliação":
            lista = sorted(lista, key=lambda p: p["avaliacao"], reverse=True)
        elif ordenar == "Nome":
            lista = sorted(lista, key=lambda p: p["nome"])
        else:
            lista = sorted(lista, key=lambda p: p["bairro"])

        st.caption(f"{len(lista)} estabelecimentos")

        # Renderiza cards em 2 colunas
        cols = st.columns(2)
        for i, p in enumerate(lista):
            cor = COR_CANAL.get(p["canal"], "#888")
            ico = ICONE_CANAL.get(p["canal"], "📍")
            with cols[i % 2]:
                aberto_txt = ""
                if p.get("aberto") is True:
                    aberto_txt = "🟢 Aberto"
                elif p.get("aberto") is False:
                    aberto_txt = "🔴 Fechado"

                tel = p.get("telefone", "")
                site = p.get("website", "")

                st.markdown(f"""
                <div class="card">
                  <div class="card-nome">{ico} {p['nome']}</div>
                  <div class="card-sub">
                    <span class="badge" style="background:{cor}22;color:{cor};border:.5px solid {cor}44">
                      {p['canal'].split('—')[0].strip()}
                    </span>
                    📍 {p['bairro']} · ⭐ {p['avaliacao']} ({p['n_aval']:,}) {aberto_txt}
                  </div>
                  <div class="card-sub" style="margin-top:4px;color:#444">{p['endereco'][:60]}</div>
                  {f'<div class="card-tel">📞 {tel}</div>' if tel and tel != "–" else ''}
                  {f'<div class="card-sub"><a href="{site}" target="_blank" style="color:#6eaaf0">🌐 {site[:40]}</a></div>' if site and site != "–" else ''}
                </div>
                """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# ABA ROTAS
# ════════════════════════════════════════════════════════════════
with aba_rotas:
    if not rotas:
        if pontos:
            st.info("Clique em **🚗 Gerar roteiro** na barra lateral para criar as rotas.")
        else:
            st.info("Faça a busca primeiro, depois gere o roteiro.")
    else:
        st.markdown(f"### {len(rotas)} rota(s) gerada(s)")
        st.caption(f"Algoritmo: Vizinho Mais Próximo · até {max_por_rota} paradas por rota")

        for i, rota in enumerate(rotas):
            stats = calcular_stats_rota(rota)
            url_gmaps = rota_para_gmaps(rota)
            cores_rota = ["#c8f06e", "#6eaaf0", "#f06eaa", "#f0b06e", "#e890ff"]
            cor_r = cores_rota[i % len(cores_rota)]

            with st.expander(
                f"🚗 Rota {i+1} · {stats['n_pontos']} paradas · ~{stats['dist_km']} km · {stats['tempo_est']}",
                expanded=(i == 0),
            ):
                # Stats da rota
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Paradas", stats["n_pontos"])
                rc2.metric("Distância est.", f"{stats['dist_km']} km")
                rc3.metric("Tempo est.", stats["tempo_est"])

                st.caption("⏱ Estimativa: 25 km/h médio + 10 min por visita")

                # Bairros da rota
                st.markdown(f"**Bairros:** {', '.join(stats['bairros'])}")

                # Canais
                canal_str = " · ".join(
                    f"{ICONE_CANAL.get(c, '📍')} {c.split('—')[0].strip()} ({n})"
                    for c, n in stats["canais"].items()
                )
                st.markdown(f"**Canais:** {canal_str}")

                # Botão Google Maps
                st.markdown(
                    f'<a href="{url_gmaps}" target="_blank" class="route-btn">'
                    f'🗺 Abrir rota completa no Google Maps</a>',
                    unsafe_allow_html=True,
                )
                st.markdown("")

                # Lista de paradas
                st.markdown("**Sequência de visitas:**")
                for j, p in enumerate(rota):
                    cor = COR_CANAL.get(p["canal"], "#888")
                    ico = ICONE_CANAL.get(p["canal"], "📍")
                    url_waze = f"https://waze.com/ul?ll={p['lat']},{p['lng']}&navigate=yes"
                    tel = p.get("telefone", "")

                    col_n, col_info, col_nav = st.columns([1, 6, 2])
                    with col_n:
                        st.markdown(
                            f'<div style="background:{cor_r};color:#000;font-family:monospace;'
                            f'font-weight:700;font-size:13px;width:28px;height:28px;'
                            f'border-radius:50%;display:flex;align-items:center;'
                            f'justify-content:center;margin-top:4px">{j+1}</div>',
                            unsafe_allow_html=True,
                        )
                    with col_info:
                        st.markdown(
                            f'<div style="font-size:13px;font-weight:600;color:#f0ede8">{ico} {p["nome"]}</div>'
                            f'<div style="font-size:11px;color:#555;font-family:monospace">'
                            f'📍 {p["bairro"]} · ⭐ {p["avaliacao"]}'
                            f'{f" · 📞 {tel}" if tel and tel != "–" else ""}</div>',
                            unsafe_allow_html=True,
                        )
                    with col_nav:
                        st.markdown(
                            f'<a href="{url_waze}" target="_blank" '
                            f'style="font-size:11px;color:#6eaaf0;text-decoration:none">🧭 Waze</a>',
                            unsafe_allow_html=True,
                        )

                    if j < len(rota) - 1:
                        st.divider()


# ════════════════════════════════════════════════════════════════
# ABA EXPORTAR
# ════════════════════════════════════════════════════════════════
with aba_export:
    if not pontos:
        st.info("Faça a busca primeiro.")
    else:
        st.markdown("### Exportar dados")

        # DataFrame completo
        df = pd.DataFrame(pontos)
        cols_export = ["nome", "bairro", "regiao", "canal", "endereco",
                       "avaliacao", "n_aval", "telefone", "website"]
        cols_ok = [c for c in cols_export if c in df.columns]
        df_export = df[cols_ok].copy()
        df_export.columns = ["Nome", "Bairro", "Região", "Canal", "Endereço",
                              "Avaliação", "Nº Aval.", "Telefone", "Site"][:len(cols_ok)]

        st.dataframe(df_export, use_container_width=True, height=300)

        # Download Excel
        import io
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Estabelecimentos")
            if rotas:
                rotas_rows = []
                for i, rota in enumerate(rotas):
                    for j, p in enumerate(rota):
                        rotas_rows.append({
                            "Rota": i + 1,
                            "Ordem": j + 1,
                            "Nome": p["nome"],
                            "Bairro": p["bairro"],
                            "Canal": p["canal"],
                            "Endereço": p["endereco"],
                            "Telefone": p.get("telefone", ""),
                            "Avaliação": p["avaliacao"],
                            "Lat": p["lat"],
                            "Lng": p["lng"],
                        })
                pd.DataFrame(rotas_rows).to_excel(
                    writer, index=False, sheet_name="Roteiro"
                )

        st.download_button(
            "📥 Baixar Excel (Estabelecimentos + Roteiro)",
            data=buf.getvalue(),
            file_name=f"gauden_prospeccao_{regiao_sel.split('—')[0].strip().lower().replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.divider()
        st.caption(
            f"📊 {len(pontos)} estabelecimentos · "
            f"{len(rotas)} rota(s) · "
            f"Gerado em {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}"
        )
