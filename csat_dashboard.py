import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter
import re

# --- Config ---
st.set_page_config(page_title="CSAT Prisma/Radar", page_icon="📊", layout="wide")

SHEETS_BASE = (
    "https://docs.google.com/spreadsheets/d/"
    "12m1m0SUwpbSckXXnqP79Y-1ipplL_s2C1ML-RASch2w"
    "/gviz/tq?tqx=out:csv&sheet="
)

USER_TYPE_LABELS = {2: "Estudante", 3: "Professor", 7: "Gestor", 17: "Gestor"}
USER_TYPE_GROUPS = {
    "Estudante (2)": [2],
    "Professor (3)": [3],
    "Gestores (7 e 17)": [7, 17],
}
GROUP_COLORS = {"Estudante (2)": "#3b82f6", "Professor (3)": "#22c55e", "Gestores (7 e 17)": "#a855f7"}
SCORE_COLORS = {1: "#ef4444", 2: "#f97316", 3: "#eab308", 4: "#84cc16", 5: "#22c55e"}
BRAND_COLORS = {"Prisma": "#6366f1", "Radar": "#f59e0b", "Ambos": "#8b5cf6"}

# KR target
KR_TARGET = 60.0

# --- Thematic analysis ---
THEMES = {
    "Bug / Erro técnico": {
        "keywords": ["trava", "travando", "erro", "bug", "falha", "cai", "caindo",
                     "não funciona", "não abre", "não atualiza", "não consigo",
                     "não carrega", "lento", "demora", "crashe", "problema"],
        "icon": "🐛",
    },
    "UX / Usabilidade": {
        "keywords": ["difícil", "confuso", "complicado", "layout", "visual",
                     "interface", "menu", "navegação", "intuitivo", "praticidade",
                     "visibilidade", "modo", "tela", "design", "fácil", "facil"],
        "icon": "🎨",
    },
    "Conteúdo / Pedagógico": {
        "keywords": ["questão", "questões", "questoes", "prova", "simulado",
                     "avaliação", "atividade", "conteúdo", "disciplina",
                     "matéria", "aula", "estudo", "estudar", "aprender",
                     "desempenho", "resultado", "relatório", "dados",
                     "estatística", "competência", "habilidade", "pista"],
        "icon": "📚",
    },
    "Feature Request": {
        "keywords": ["adicionar", "colocar", "poderia", "queria", "melhorar",
                     "liberar", "disponibilizar", "ter", "falta", "precisar",
                     "incluir", "criar", "implementar", "opção", "upgrade"],
        "icon": "💡",
    },
    "Gamificação / Engajamento": {
        "keywords": ["jogo", "jogar", "quiz", "eureka", "animação", "animacoes",
                     "confete", "divertido", "personagem", "interativo"],
        "icon": "🎮",
    },
    "Login / Acesso": {
        "keywords": ["login", "logado", "senha", "acessar", "acesso", "entrar",
                     "cadastro", "autenticação"],
        "icon": "🔐",
    },
    "Elogio / Satisfação": {
        "keywords": ["bom", "boa", "ótimo", "ótima", "perfeito", "maravilhos",
                     "incrível", "amei", "demais", "legal", "satisfeit",
                     "excelente", "parabéns", "melhor", "adoro", "gostei",
                     "nada a", "tudo ok", "tudo bem", "ta bom", "tá bom",
                     "está bom", "já está"],
        "icon": "💚",
    },
}

STOPWORDS = {
    "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com",
    "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como",
    "mas", "foi", "ao", "ele", "das", "tem", "à", "seu", "sua", "ou", "ser",
    "quando", "muito", "há", "nos", "já", "eu", "também", "só", "pelo", "pela",
    "até", "isso", "ela", "entre", "era", "depois", "sem", "mesmo", "aos",
    "ter", "seus", "quem", "nas", "me", "esse", "eles", "estão", "você",
    "tinha", "foram", "essa", "num", "nem", "suas", "meu", "às", "minha",
    "têm", "numa", "pelos", "elas", "havia", "seja", "qual", "será", "nós",
    "tenho", "lhe", "deles", "essas", "esses", "pelas", "este", "fosse",
    "dele", "tu", "te", "vocês", "vos", "lhes", "meus", "minhas", "teu",
    "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas", "dela",
    "delas", "esta", "estes", "estas", "aquele", "aquela", "aqueles",
    "aquelas", "isto", "aquilo", "estou", "está", "estamos", "estão",
    "estive", "esteve", "estivemos", "estiveram", "estava", "estávamos",
    "estavam", "sou", "somos", "são", "fui", "fomos", "seria", "pra",
    "pro", "nao", "sim", "porque", "pois", "então", "ainda", "la", "lá",
    "aí", "ai", "ali", "aqui", "bem", "uns", "umas", "todo", "toda",
    "todos", "todas", "cada", "outra", "outro", "outros", "outras",
    "nada", "algo", "coisa", "sei", "sla", "tipo", "acho", "oi",
}


# --- Data loading ---
@st.cache_data(ttl=3600)
def load_data_from_sheets() -> pd.DataFrame:
    df_prisma = pd.read_csv(SHEETS_BASE + "CSAT_Prisma")
    df_prisma["produto"] = "Prisma"

    df_radar = pd.read_csv(SHEETS_BASE + "CSAT_Radar")
    df_radar["produto"] = "Radar"

    # Normalize columns (Radar has different column order and extra empty cols)
    target_cols = [
        "score", "comment", "business_unit_id", "school_id",
        "account_id", "user_type_id", "profile_id", "user_id",
        "Submitted At", "Token", "produto",
    ]
    df_prisma = _normalize_columns(df_prisma, target_cols)
    df_radar = _normalize_columns(df_radar, target_cols)

    df = pd.concat([df_prisma, df_radar], ignore_index=True)
    return _process_df(df)


@st.cache_data
def load_data_from_file(file) -> pd.DataFrame:
    df = pd.read_csv(file, encoding="utf-8")
    df["produto"] = "CSV"
    return _process_df(df)


def _normalize_columns(df: pd.DataFrame, target_cols: list) -> pd.DataFrame:
    col_score = df.columns[0]
    col_comment = df.columns[1]
    df = df.rename(columns={col_score: "score", col_comment: "comment"})

    # Keep only relevant columns
    keep = [c for c in df.columns if c in target_cols or c in [
        "business_unit_id", "school_id", "account_id",
        "user_type_id", "profile_id", "user_id", "Submitted At", "Token"
    ]]
    df = df[[c for c in keep if c in df.columns]].copy()

    for col in target_cols:
        if col not in df.columns:
            df[col] = None
    return df[target_cols]


def _process_df(df: pd.DataFrame) -> pd.DataFrame:
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["score"])
    df["score"] = df["score"].astype(int)
    df = df[df["score"].between(1, 5)]
    df["user_type_id"] = pd.to_numeric(df["user_type_id"], errors="coerce").astype("Int64")
    df["submitted_at"] = pd.to_datetime(df["Submitted At"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df["date"] = df["submitted_at"].dt.date
    df["week"] = df["submitted_at"].dt.to_period("W").apply(lambda r: r.start_time)
    df["user_type_label"] = df["user_type_id"].map(USER_TYPE_LABELS).fillna("Outro")
    df["comment"] = df["comment"].fillna("").astype(str).str.strip()
    return df


# --- Helpers ---
def pct(mask, total):
    return (mask.sum() / total * 100) if total > 0 else 0


def classify_themes(text):
    lower = text.lower()
    found = []
    for theme, cfg in THEMES.items():
        if any(k in lower for k in cfg["keywords"]):
            found.append(theme)
    return found


def extract_keywords(texts, top_n=15):
    words = Counter()
    for text in texts:
        clean = re.sub(r'[^\wáàâãéèêíïóôõúüç]', ' ', text.lower())
        for word in clean.split():
            if len(word) > 2 and word not in STOPWORDS:
                words[word] += 1
    return words.most_common(top_n)


def get_group_for_type(ut):
    for gname, ids in USER_TYPE_GROUPS.items():
        if ut in ids:
            return gname
    return "Outro"


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.title("📊 CSAT Prisma/Radar")

data_source = st.sidebar.radio("Fonte de dados", ["Google Sheets (automático)", "Upload CSV"], index=0)

df = None
if data_source == "Google Sheets (automático)":
    try:
        with st.spinner("Buscando dados do Google Sheets..."):
            df = load_data_from_sheets()
        st.sidebar.success(f"{len(df)} respostas carregadas")
        if st.sidebar.button("🔄 Atualizar dados"):
            st.cache_data.clear()
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro ao acessar Sheets: {e}")
        data_source = "Upload CSV"

if data_source == "Upload CSV":
    uploaded_file = st.sidebar.file_uploader("Carregar CSV", type=["csv"])
    if uploaded_file is None:
        st.title("📊 CSAT Prisma/Radar")
        st.info("Faça upload do CSV na barra lateral para começar.")
        st.stop()
    df = load_data_from_file(uploaded_file)

if df is None or df.empty:
    st.stop()

# --- Filters ---
st.sidebar.markdown("---")
st.sidebar.subheader("Filtros")

# Product filter
produtos_disponiveis = sorted(df["produto"].unique())
selected_produtos = st.sidebar.multiselect(
    "Produto",
    options=produtos_disponiveis,
    default=produtos_disponiveis,
)

# Multi-select user type
selected_groups = st.sidebar.multiselect(
    "Perfil de usuário",
    options=list(USER_TYPE_GROUPS.keys()),
    default=list(USER_TYPE_GROUPS.keys()),
)
selected_user_types = []
for g in selected_groups:
    selected_user_types.extend(USER_TYPE_GROUPS[g])

# Date range
min_date = df["date"].min()
max_date = df["date"].max()
period_option = st.sidebar.selectbox(
    "Período",
    ["Todo o período", "Últimos 7 dias", "Últimos 14 dias", "Últimos 30 dias", "Personalizado"],
)
if period_option == "Personalizado":
    date_range = st.sidebar.date_input("Intervalo", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date
elif period_option == "Todo o período":
    start_date, end_date = min_date, max_date
else:
    days = int(period_option.split()[1])
    end_date = max_date
    start_date = max_date - timedelta(days=days)

# Apply filters
mask = (
    df["user_type_id"].isin(selected_user_types)
    & df["produto"].isin(selected_produtos)
    & (df["date"] >= start_date)
    & (df["date"] <= end_date)
)
filtered = df[mask].copy()

if filtered.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados.")
    st.stop()


# ============================================================
# KR TRACKER (always visible, uses full unfiltered data)
# ============================================================
st.title("📊 CSAT Prisma/Radar")

# KR: nota 5 de Gestores (7+17) + Professores (3), ambas marcas
kr_types = [3, 7, 17]
kr_data = df[df["user_type_id"].isin(kr_types)]
kr_total = len(kr_data)
kr_top5 = pct(kr_data["score"] == 5, kr_total) if kr_total > 0 else 0
kr_delta = kr_top5 - KR_TARGET
kr_status = "✅" if kr_top5 >= KR_TARGET else "🔴"

kr_col1, kr_col2, kr_col3 = st.columns([2, 1, 1])
with kr_col1:
    st.markdown(
        f"### {kr_status} KR: Excelência (nota 5) Gestores + Professores"
    )
    st.caption(f"Meta: ≥ {KR_TARGET:.0f}% | Ambas as marcas | user_type_id 3, 7, 17")
with kr_col2:
    st.metric("Atual", f"{kr_top5:.1f}%", delta=f"{kr_delta:+.1f}pp vs meta")
with kr_col3:
    # KR by product
    for prod in sorted(df["produto"].unique()):
        prod_kr = df[(df["user_type_id"].isin(kr_types)) & (df["produto"] == prod)]
        if len(prod_kr) > 0:
            v = pct(prod_kr["score"] == 5, len(prod_kr))
            icon = "✅" if v >= KR_TARGET else "🔴"
            st.markdown(f"{icon} **{prod}:** {v:.1f}% ({len(prod_kr)} resp.)")

st.markdown("---")

# --- Caption ---
st.caption(
    f"Exibindo {len(filtered)} respostas | "
    f"{'  '.join(selected_produtos)} | "
    f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
)

# ============================================================
# KPIs
# ============================================================
total = len(filtered)
csat_45 = pct(filtered["score"] >= 4, total)
top_box = pct(filtered["score"] == 5, total)
detractors = pct(filtered["score"] <= 2, total)
avg_score = filtered["score"].mean()
comments_count = (filtered["comment"].str.len() > 3).sum()

not5 = pct(filtered["score"] != 5, total)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Respostas", f"{total}")
k2.metric("% Nota 5 (Excelência)", f"{top_box:.1f}%")
k3.metric("CSAT (4+5)", f"{csat_45:.1f}%")
k4.metric("% Não-5 (oportunidade)", f"{not5:.1f}%")
k5.metric("Detratores (1+2)", f"{detractors:.1f}%")
k6.metric("Nota Média", f"{avg_score:.2f}")


# ============================================================
# BREAKDOWN TABLE
# ============================================================
st.markdown("---")
st.subheader("Breakdown por perfil e produto")

breakdown_rows = []
for group_name, type_ids in USER_TYPE_GROUPS.items():
    for prod in sorted(filtered["produto"].unique()):
        gd = filtered[(filtered["user_type_id"].isin(type_ids)) & (filtered["produto"] == prod)]
        if gd.empty:
            continue
        n = len(gd)
        breakdown_rows.append({
            "Perfil": group_name,
            "Produto": prod,
            "Respostas": n,
            "% CSAT (4+5)": round(pct(gd["score"] >= 4, n), 1),
            "% Top Box (5)": round(pct(gd["score"] == 5, n), 1),
            "% Detratores (1+2)": round(pct(gd["score"] <= 2, n), 1),
            "Nota Média": round(gd["score"].mean(), 2),
        })

if breakdown_rows:
    bdf = pd.DataFrame(breakdown_rows)
    st.dataframe(bdf, use_container_width=True, hide_index=True)


# ============================================================
# CHARTS
# ============================================================
st.markdown("---")
col_trend, col_dist = st.columns(2)

with col_trend:
    st.subheader("Tendência CSAT semanal")
    weekly = filtered.groupby("week").agg(
        total=("score", "count"),
        csat_45=("score", lambda x: (x >= 4).sum() / len(x) * 100),
        top_box=("score", lambda x: (x == 5).sum() / len(x) * 100),
    ).reset_index().sort_values("week")

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=weekly["week"], y=weekly["top_box"], name="% Nota 5 (Excelência)",
        mode="lines+markers", line=dict(color="#3b82f6", width=3),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.15)"
    ))
    fig_trend.add_trace(go.Scatter(
        x=weekly["week"], y=weekly["csat_45"], name="% CSAT (4+5)",
        mode="lines+markers", line=dict(color="#22c55e", width=1.5, dash="dot"),
    ))
    fig_trend.add_hline(y=KR_TARGET, line_dash="dash", line_color="#a855f7",
                        annotation_text=f"Meta KR ({KR_TARGET:.0f}%)")
    fig_trend.update_layout(
        yaxis=dict(range=[0, 100], ticksuffix="%"),
        template="plotly_dark", height=400, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

with col_dist:
    st.subheader("Distribuição de notas")
    dist = filtered["score"].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0).reset_index()
    dist.columns = ["Nota", "Respostas"]
    fig_dist = px.bar(dist, x="Nota", y="Respostas", color="Nota",
                      color_discrete_map=SCORE_COLORS, text_auto=True)
    fig_dist.update_layout(template="plotly_dark", height=400, showlegend=False,
                           margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_dist, use_container_width=True)

col_ut, col_prod = st.columns(2)

with col_ut:
    st.subheader("% Nota 5 por perfil — Tendência")
    fig_ut = go.Figure()
    for group_name, type_ids in USER_TYPE_GROUPS.items():
        gd = filtered[filtered["user_type_id"].isin(type_ids)]
        if gd.empty:
            continue
        wut = gd.groupby("week").agg(
            top5=("score", lambda x: (x == 5).sum() / len(x) * 100),
        ).reset_index().sort_values("week")
        fig_ut.add_trace(go.Scatter(
            x=wut["week"], y=wut["top5"], name=group_name,
            mode="lines+markers", line=dict(color=GROUP_COLORS.get(group_name, "#888"), width=2),
        ))
    fig_ut.add_hline(y=KR_TARGET, line_dash="dash", line_color="#a855f7",
                     annotation_text=f"Meta KR ({KR_TARGET:.0f}%)")
    fig_ut.update_layout(
        yaxis=dict(range=[0, 100], ticksuffix="%"),
        template="plotly_dark", height=400, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_ut, use_container_width=True)

with col_prod:
    st.subheader("% Nota 5 por produto — Tendência")
    fig_prod = go.Figure()
    for prod in sorted(filtered["produto"].unique()):
        pd_data = filtered[filtered["produto"] == prod]
        wprod = pd_data.groupby("week").agg(
            top5=("score", lambda x: (x == 5).sum() / len(x) * 100),
        ).reset_index().sort_values("week")
        fig_prod.add_trace(go.Scatter(
            x=wprod["week"], y=wprod["top5"], name=prod,
            mode="lines+markers",
            line=dict(color=BRAND_COLORS.get(prod, "#888"), width=2),
        ))
    fig_prod.add_hline(y=KR_TARGET, line_dash="dash", line_color="#a855f7",
                       annotation_text=f"Meta KR ({KR_TARGET:.0f}%)")
    fig_prod.update_layout(
        yaxis=dict(range=[0, 100], ticksuffix="%"),
        template="plotly_dark", height=400, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_prod, use_container_width=True)


# ============================================================
# DEEP INSIGHTS — THEMATIC ANALYSIS
# ============================================================
st.markdown("---")
st.subheader("🔍 Análise temática dos comentários")

comments_all = filtered[filtered["comment"].str.len() > 3].copy()
comments_all["themes"] = comments_all["comment"].apply(classify_themes)

if len(comments_all) > 0:
    # --- Global theme distribution ---
    theme_counts = Counter()
    for themes in comments_all["themes"]:
        for t in themes:
            theme_counts[t] += 1

    if theme_counts:
        col_themes, col_words = st.columns(2)

        with col_themes:
            st.markdown("**Temas mais mencionados (todos os perfis)**")
            theme_df = pd.DataFrame([
                {"Tema": f"{THEMES[t]['icon']} {t}", "Menções": c,
                 "% dos comentários": round(c / len(comments_all) * 100, 1)}
                for t, c in theme_counts.most_common()
            ])
            st.dataframe(theme_df, use_container_width=True, hide_index=True)

        with col_words:
            st.markdown("**Palavras mais frequentes nos comentários**")
            kws = extract_keywords(comments_all["comment"].tolist(), top_n=20)
            if kws:
                kw_df = pd.DataFrame(kws, columns=["Palavra", "Frequência"])
                fig_kw = px.bar(kw_df, x="Frequência", y="Palavra", orientation="h",
                                text_auto=True)
                fig_kw.update_traces(marker_color="#6366f1")
                fig_kw.update_layout(template="plotly_dark", height=450,
                                     margin=dict(l=0, r=0, t=10, b=0),
                                     yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_kw, use_container_width=True)

    # --- Per persona deep dive ---
    st.markdown("---")
    st.subheader("👥 Diagnóstico por persona")

    for group_name, type_ids in USER_TYPE_GROUPS.items():
        gc = comments_all[comments_all["user_type_id"].isin(type_ids)]
        gall = filtered[filtered["user_type_id"].isin(type_ids)]
        if gc.empty:
            continue

        n_total = len(gall)
        n_comments = len(gc)
        g_csat = pct(gall["score"] >= 4, n_total)
        g_top5 = pct(gall["score"] == 5, n_total)
        g_det = pct(gall["score"] <= 2, n_total)

        color = GROUP_COLORS.get(group_name, "#888")
        st.markdown(f"### {group_name}")

        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Respostas", n_total)
        pc2.metric("CSAT (4+5)", f"{g_csat:.1f}%")
        pc3.metric("Top Box (5)", f"{g_top5:.1f}%")
        pc4.metric("Comentários", n_comments)

        # Theme breakdown for this persona
        p_themes = Counter()
        for themes in gc["themes"]:
            for t in themes:
                p_themes[t] += 1

        # Split: pain points vs positive
        pain_themes = {t: c for t, c in p_themes.items() if t != "Elogio / Satisfação"}
        praise_count = p_themes.get("Elogio / Satisfação", 0)

        ptcol1, ptcol2 = st.columns(2)

        with ptcol1:
            st.markdown("**🔴 Dores e pedidos**")
            if pain_themes:
                for theme, count in sorted(pain_themes.items(), key=lambda x: -x[1]):
                    icon = THEMES[theme]["icon"]
                    pct_val = count / n_comments * 100
                    st.markdown(f"- {icon} **{theme}**: {count} menções ({pct_val:.0f}% dos comentários)")

                    # Show top examples for this theme
                    theme_examples = gc[gc["themes"].apply(lambda x: theme in x)]
                    # Prioritize detractor comments
                    theme_examples = theme_examples.sort_values("score")
                    examples = theme_examples.head(3)
                    for _, row in examples.iterrows():
                        score_emoji = "🔴" if row["score"] <= 2 else "🟡" if row["score"] == 3 else "🟢"
                        prod_tag = f"[{row['produto']}]" if "produto" in row and pd.notna(row["produto"]) else ""
                        st.caption(f"  {score_emoji} Nota {row['score']} {prod_tag} (account: {row['account_id']}): \"{row['comment'][:120]}\"")
            else:
                st.caption("Nenhuma dor identificada nos comentários.")

        with ptcol2:
            st.markdown("**🟢 O que funciona bem**")
            if praise_count > 0:
                st.markdown(f"- 💚 **{praise_count} elogios** ({praise_count/n_comments*100:.0f}% dos comentários)")
                praise_examples = gc[gc["themes"].apply(lambda x: "Elogio / Satisfação" in x)].sort_values("score", ascending=False).head(3)
                for _, row in praise_examples.iterrows():
                    prod_tag = f"[{row['produto']}]" if "produto" in row and pd.notna(row["produto"]) else ""
                    st.caption(f"  💚 Nota {row['score']} {prod_tag} (account: {row['account_id']}): \"{row['comment'][:120]}\"")

            # Keywords specific to this persona
            st.markdown("**Palavras-chave da persona**")
            p_kws = extract_keywords(gc["comment"].tolist(), top_n=10)
            if p_kws:
                st.caption(" | ".join([f"**{w}** ({c})" for w, c in p_kws]))

        # Detractor deep-dive for this persona
        det_comments = gc[gc["score"] <= 2]
        if len(det_comments) > 0:
            with st.expander(f"🔴 {len(det_comments)} comentários de detratores — {group_name}", expanded=False):
                for _, row in det_comments.sort_values("score").iterrows():
                    themes_str = " ".join([THEMES[t]["icon"] for t in row["themes"]]) if row["themes"] else ""
                    prod_tag = f"[{row['produto']}]" if pd.notna(row.get("produto")) else ""
                    st.markdown(
                        f"**Nota {row['score']}** {prod_tag} {themes_str} — {row['comment']}  \n"
                        f"<sub>{row['submitted_at'].strftime('%d/%m/%Y') if pd.notna(row['submitted_at']) else ''} "
                        f"| school: {row['school_id']} | account: {row['account_id']}</sub>",
                        unsafe_allow_html=True,
                    )

        st.markdown("---")


# ============================================================
# ACTIONABLE INSIGHTS SUMMARY
# ============================================================
st.subheader("📋 Resumo executivo — O que os dados dizem")

insights = []

# KR status
if kr_top5 >= KR_TARGET:
    insights.append(f"✅ **KR on track:** Excelência (nota 5) de Gestores + Professores está em {kr_top5:.1f}% (meta: {KR_TARGET:.0f}%)")
else:
    gap = KR_TARGET - kr_top5
    insights.append(f"🔴 **KR at risk:** Excelência (nota 5) de Gestores + Professores está em {kr_top5:.1f}% — faltam {gap:.1f}pp para a meta de {KR_TARGET:.0f}%")

# Best/worst persona by nota 5
if len(breakdown_rows) >= 2:
    sorted_br = sorted(breakdown_rows, key=lambda x: x["% Top Box (5)"], reverse=True)
    best = sorted_br[0]
    worst = sorted_br[-1]
    insights.append(f"🏆 **Maior % nota 5:** {best['Perfil']} ({best['Produto']}) com {best['% Top Box (5)']}%")
    insights.append(f"⚠️ **Menor % nota 5:** {worst['Perfil']} ({worst['Produto']}) com {worst['% Top Box (5)']}%")

# Product comparison — nota 5
for prod in sorted(filtered["produto"].unique()):
    pd_all = filtered[filtered["produto"] == prod]
    if len(pd_all) > 0:
        p5 = pct(pd_all["score"] == 5, len(pd_all))
        pc = pct(pd_all["score"] >= 4, len(pd_all))
        icon5 = "✅" if p5 >= KR_TARGET else "⚠️"
        insights.append(f"{icon5} **{prod}:** Nota 5 = {p5:.1f}% | CSAT 4+5 = {pc:.1f}% ({len(pd_all)} respostas)")

# Who is NOT giving 5 — opportunity gap
not5_data = filtered[filtered["score"] != 5]
if len(not5_data) > 0:
    not5_by_score = not5_data["score"].value_counts().sort_index()
    not5_str = ", ".join([f"nota {s}: {c}" for s, c in not5_by_score.items()])
    insights.append(f"🎯 **Oportunidade ({len(not5_data)} respostas não-5):** {not5_str}")

# Trend — nota 5
if len(weekly) >= 2:
    last_w = weekly.iloc[-1]["top_box"]
    prev_w = weekly.iloc[-2]["top_box"]
    diff = last_w - prev_w
    if abs(diff) > 1:
        emoji = "📈" if diff > 0 else "📉"
        direction = "subindo" if diff > 0 else "caindo"
        insights.append(f"{emoji} **Tendência nota 5 {direction}:** última semana {last_w:.1f}% vs anterior {prev_w:.1f}% ({diff:+.1f}pp)")
    else:
        insights.append(f"➡️ **Nota 5 estável:** {last_w:.1f}% vs {prev_w:.1f}% semana anterior")

# Top pain point
if theme_counts:
    pain_only = {t: c for t, c in theme_counts.items() if t != "Elogio / Satisfação"}
    if pain_only:
        top_pain = max(pain_only, key=pain_only.get)
        insights.append(f"{THEMES[top_pain]['icon']} **Principal dor:** {top_pain} ({pain_only[top_pain]} menções)")

# Bug count
bug_count = theme_counts.get("Bug / Erro técnico", 0)
if bug_count > 0:
    insights.append(f"🐛 **{bug_count} relatos de problemas técnicos** — verificar com engenharia")

for insight in insights:
    st.markdown(f"- {insight}")


# ============================================================
# NOT-5 ANALYSIS — What's blocking excellence?
# ============================================================
st.markdown("---")
st.subheader("🎯 O que impede a nota 5?")
st.caption("Comentários de quem deu nota 1 a 4 — entender essas dores é o caminho para aumentar a excelência")

not5_comments = comments_all[comments_all["score"] < 5].copy() if len(comments_all) > 0 else pd.DataFrame()

if len(not5_comments) > 0:
    # Split by score bucket
    n4_col, n3_col, n12_col = st.columns(3)

    with n4_col:
        n4 = not5_comments[not5_comments["score"] == 4]
        st.markdown(f"**Nota 4 — Quase lá ({len(n4)} comentários)**")
        st.caption("Pequenos ajustes podem converter em nota 5")
        if len(n4) > 0:
            n4_themes = Counter()
            for themes in n4["themes"]:
                for t in themes:
                    if t != "Elogio / Satisfação":
                        n4_themes[t] += 1
            for t, c in n4_themes.most_common(3):
                st.markdown(f"- {THEMES[t]['icon']} {t}: {c}x")
            for _, row in n4.head(5).iterrows():
                if row["comment"]:
                    st.caption(f"  \"{row['comment'][:100]}\" — account: {row['account_id']}")

    with n3_col:
        n3 = not5_comments[not5_comments["score"] == 3]
        st.markdown(f"**Nota 3 — Neutros ({len(n3)} comentários)**")
        st.caption("Indiferentes — risco de churn ou oportunidade")
        if len(n3) > 0:
            n3_themes = Counter()
            for themes in n3["themes"]:
                for t in themes:
                    if t != "Elogio / Satisfação":
                        n3_themes[t] += 1
            for t, c in n3_themes.most_common(3):
                st.markdown(f"- {THEMES[t]['icon']} {t}: {c}x")
            for _, row in n3.head(5).iterrows():
                if row["comment"]:
                    st.caption(f"  \"{row['comment'][:100]}\" — account: {row['account_id']}")

    with n12_col:
        n12 = not5_comments[not5_comments["score"] <= 2]
        st.markdown(f"**Nota 1-2 — Detratores ({len(n12)} comentários)**")
        st.caption("Frustração alta — ação imediata recomendada")
        if len(n12) > 0:
            n12_themes = Counter()
            for themes in n12["themes"]:
                for t in themes:
                    if t != "Elogio / Satisfação":
                        n12_themes[t] += 1
            for t, c in n12_themes.most_common(3):
                st.markdown(f"- {THEMES[t]['icon']} {t}: {c}x")
            for _, row in n12.head(5).iterrows():
                if row["comment"]:
                    st.caption(f"  \"{row['comment'][:100]}\" — account: {row['account_id']}")
else:
    st.success("Todos os comentários são nota 5!")


# ============================================================
# ALL COMMENTS (searchable)
# ============================================================
st.markdown("---")
st.subheader("💬 Todos os comentários")

ccol1, ccol2, ccol3 = st.columns([2, 1, 1])
with ccol1:
    search_term = st.text_input("🔎 Buscar nos comentários", placeholder="Digite para filtrar...")
with ccol2:
    comment_filter = st.selectbox("Filtrar por nota", ["Todos", "Detratores (1-2)", "Neutros (3)", "Promotores (4-5)"])
with ccol3:
    theme_filter = st.selectbox("Filtrar por tema", ["Todos"] + list(THEMES.keys()))

display_comments = comments_all.copy()
if search_term:
    display_comments = display_comments[display_comments["comment"].str.lower().str.contains(search_term.lower(), na=False)]
if comment_filter == "Detratores (1-2)":
    display_comments = display_comments[display_comments["score"] <= 2]
elif comment_filter == "Neutros (3)":
    display_comments = display_comments[display_comments["score"] == 3]
elif comment_filter == "Promotores (4-5)":
    display_comments = display_comments[display_comments["score"] >= 4]
if theme_filter != "Todos":
    display_comments = display_comments[display_comments["themes"].apply(lambda x: theme_filter in x)]

display_comments = display_comments.sort_values("submitted_at", ascending=False)

st.caption(f"{len(display_comments)} comentários encontrados")

for group_name, type_ids in USER_TYPE_GROUPS.items():
    group_comments = display_comments[display_comments["user_type_id"].isin(type_ids)]
    if group_comments.empty:
        continue

    with st.expander(f"{group_name} — {len(group_comments)} comentários", expanded=False):
        for _, row in group_comments.iterrows():
            score = row["score"]
            if score >= 4:
                color = "green"
            elif score == 3:
                color = "orange"
            else:
                color = "red"

            themes_tags = " ".join([f"`{THEMES[t]['icon']} {t}`" for t in row["themes"]]) if row["themes"] else ""
            prod_tag = f"**[{row['produto']}]**" if pd.notna(row.get("produto")) else ""

            st.markdown(
                f":{color}[**Nota {score}**] {prod_tag} — {row['comment']}  \n"
                f"<sub>{row['submitted_at'].strftime('%d/%m/%Y %H:%M') if pd.notna(row['submitted_at']) else ''} "
                f"| school: {row['school_id']} | account: {row['account_id']} {themes_tags}</sub>",
                unsafe_allow_html=True,
            )
