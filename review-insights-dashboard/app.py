"""Review Insights Dashboard
Streamlit app that sends customer reviews to an n8n workflow.
n8n asks Google Gemini to tag each review (sentiment + topic) and to find the top 3 issues.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Review Insights Dashboard", page_icon="📊", layout="wide")

# ---------- Colors ----------
PURPLE = "#7C3AED"
GREEN, YELLOW, RED = "#22C55E", "#F5B700", "#EF4444"
SENTIMENT_COLORS = {"positive": GREEN, "neutral": YELLOW, "negative": RED}
SENTIMENT_ORDER = ["positive", "neutral", "negative"]

# The n8n webhook URL lives in Streamlit "Secrets", never in the code.
WEBHOOK_URL = st.secrets.get("N8N_WEBHOOK_URL", "")

# ---------- Styling ----------
st.markdown(f"""
<style>
.block-container {{ padding-top: 2rem; max-width: 1250px; }}
h1, h2, h3 {{ color: #1F2937; }}
[class*="st-key-card"] {{
    background: #FFFFFF; border: none !important; border-radius: 18px;
    box-shadow: 0 4px 20px rgba(76, 29, 149, 0.07); padding: 1.1rem 1.3rem;
}}
.subtitle {{ color: #6B7280; font-size: 1.05rem; margin-top: -0.6rem; margin-bottom: 1.2rem; }}
.instructions {{
    background: #FFFFFF; border-left: 5px solid {PURPLE}; border-radius: 14px;
    box-shadow: 0 4px 20px rgba(76, 29, 149, 0.07); padding: 1rem 1.4rem; margin-bottom: 1.2rem;
}}
.instructions h4 {{ margin: 0 0 0.4rem 0; color: {PURPLE}; font-size: 1.05rem; }}
.instructions ul {{ margin: 0; padding-left: 1.2rem; color: #374151; }}
.kpi {{
    background: #FFFFFF; border-radius: 18px; padding: 1.1rem 1.3rem;
    box-shadow: 0 4px 20px rgba(76, 29, 149, 0.07);
    display: flex; justify-content: space-between; align-items: center;
}}
.kpi-label {{ color: #6B7280; font-size: 0.9rem; }}
.kpi-value {{ font-size: 2rem; font-weight: 700; color: #111827; line-height: 1.2; }}
.kpi-sub {{ font-size: 0.8rem; font-weight: 600; }}
.card-title {{ font-weight: 700; font-size: 1.05rem; color: #1F2937; margin-bottom: 0.3rem; }}
.topic-row {{ display: flex; align-items: center; gap: 0.8rem; margin: 0.55rem 0; }}
.topic-name {{ width: 130px; font-size: 0.9rem; color: #374151; }}
.topic-bar {{ flex: 1; height: 8px; border-radius: 6px; background: #EEEAF8; display: flex; overflow: hidden; }}
.topic-count {{ width: 32px; text-align: right; font-size: 0.85rem; color: #6B7280; }}
.issue {{ border-top: 4px solid {RED}; }}
.issue-mentions {{ display: inline-block; background: #FDECEC; color: {RED}; border-radius: 20px;
    padding: 2px 10px; font-size: 0.78rem; font-weight: 600; margin: 0.2rem 0 0.5rem 0; }}
.tip {{ background: #F3EEFF; border-radius: 10px; padding: 0.6rem 0.8rem; font-size: 0.88rem; color: #4C1D95; }}
.legend-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin: 0 4px 0 12px; }}
</style>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
def find_column(df: pd.DataFrame, names: list[str]) -> str | None:
    for col in df.columns:
        if col.strip().lower() in names:
            return col
    return None


def ring(percent: float, color: str, label: str | None = None) -> str:
    """Small circular progress ring (SVG) like the KPI cards in the design."""
    r, c = 26, 2 * 3.1416 * 26
    dash = c * max(0, min(percent, 100)) / 100
    return f"""
    <svg width="68" height="68" viewBox="0 0 68 68">
      <circle cx="34" cy="34" r="{r}" fill="none" stroke="#EEEAF8" stroke-width="7"/>
      <circle cx="34" cy="34" r="{r}" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round"
              stroke-dasharray="{dash} {c}" transform="rotate(-90 34 34)"/>
      <text x="34" y="39" text-anchor="middle" font-size="13" font-weight="700" fill="{color}">{label or f"{percent:.0f}%"}</text>
    </svg>"""


def kpi_card(label: str, value: str, sub: str, percent: float, color: str, ring_label: str | None = None) -> str:
    return f"""
    <div class="kpi">
      <div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub" style="color:{color}">{sub}</div>
      </div>
      {ring(percent, color, ring_label)}
    </div>"""


def style_fig(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#374151"), legend_title=None,
        legend=dict(orientation="h", y=-0.15, x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#F0EDF8")
    return fig


def call_n8n(reviews: list[dict]) -> dict:
    resp = requests.post(WEBHOOK_URL, json={"reviews": reviews}, timeout=180)
    resp.raise_for_status()
    return resp.json()


# ---------- Header ----------
st.title("Review Insights Dashboard")
st.markdown('<div class="subtitle">Upload your reviews and get a dashboard summarizing the insights. '
            'You can download the results 😉</div>', unsafe_allow_html=True)

st.markdown("""
<div class="instructions">
  <h4>📋 Instructions</h4>
  <ul>
    <li>Upload your CSV with your reviews.</li>
    <li>It needs to have at least the following columns: <b>Date</b>, <b>Rating</b> (number), <b>Review</b> (text).</li>
    <li>CSV file with one review per row.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

if not WEBHOOK_URL:
    st.error("The n8n webhook URL is missing. Add N8N_WEBHOOK_URL in the app's Secrets.")
    st.stop()

# ---------- Input ----------
reviews: list[dict] = []
meta: dict[str, dict] = {}

with st.container(key="card_input"):
    tab_csv, tab_text = st.tabs(["📄 Upload CSV", "✍️ Paste reviews"])
    with tab_csv:
        file = st.file_uploader("Choose a CSV file", type=["csv"])
        if file is not None:
            df_in = pd.read_csv(file)
            text_col = find_column(df_in, ["review", "review_text", "text", "comment", "comentario", "reseña", "resena"])
            date_col = find_column(df_in, ["date", "fecha"])
            rating_col = find_column(df_in, ["rating", "stars", "puntuacion", "puntuación"])
            id_col = find_column(df_in, ["review_id", "id"])
            if text_col is None:
                st.error("I couldn't find the review column. Please name it **Review**.")
            else:
                missing = [n for n, c in [("Date", date_col), ("Rating", rating_col)] if c is None]
                if missing:
                    st.warning(f"Missing column(s): {', '.join(missing)}. The analysis still works, "
                               "but some charts will be hidden.")
                st.caption(f"{len(df_in)} reviews found")
                st.dataframe(df_in.head(5), width="stretch", hide_index=True)
                for i, row in df_in.iterrows():
                    text = str(row[text_col]).strip()
                    if not text or text.lower() == "nan":
                        continue
                    rid = str(row[id_col]) if id_col else f"R{i + 1:03d}"
                    reviews.append({"review_id": rid, "review_text": text})
                    meta[rid] = {
                        "date": row[date_col] if date_col else None,
                        "rating": row[rating_col] if rating_col else None,
                    }
    with tab_text:
        pasted = st.text_area("One review per line", height=160,
                              placeholder="The product arrived late...\nGreat quality, I love it...")
        if pasted.strip() and not reviews:
            lines = [l.strip() for l in pasted.splitlines() if l.strip()]
            reviews = [{"review_id": f"R{i + 1:03d}", "review_text": l} for i, l in enumerate(lines)]

    analyze = st.button("Analyze reviews", type="primary", disabled=not reviews)

if analyze:
    with st.spinner(f"AI is reading {len(reviews)} reviews... this can take up to a minute"):
        try:
            st.session_state["data"] = call_n8n(reviews)
            st.session_state["meta"] = meta
        except requests.exceptions.Timeout:
            st.error("The analysis took too long. Please try again.")
        except Exception as e:
            st.error(f"Something went wrong during the analysis: {e}")

data = st.session_state.get("data")
if not data:
    st.stop()

# ---------- Prepare results ----------
meta = st.session_state.get("meta", {})
df = pd.DataFrame(data["results"])
df["topic"] = df["topic"].str.replace("_", " ").str.capitalize()
df["date"] = pd.to_datetime(df["review_id"].map(lambda r: meta.get(r, {}).get("date")), errors="coerce")
df["rating"] = pd.to_numeric(df["review_id"].map(lambda r: meta.get(r, {}).get("rating")), errors="coerce")
counts = {s: int((df["sentiment"] == s).sum()) for s in SENTIMENT_ORDER}
total = len(df)
pct = {s: 100 * counts[s] / total for s in SENTIMENT_ORDER}

st.markdown("### Results")

# ---------- KPI cards ----------
k1, k2, k3, k4 = st.columns(4)
if df["rating"].notna().any():
    avg = df["rating"].mean()
    k1.markdown(kpi_card("Total reviews", str(total), "average rating", avg / 5 * 100, PURPLE, f"{avg:.1f}★"),
                unsafe_allow_html=True)
else:
    k1.markdown(kpi_card("Total reviews", str(total), "analyzed by AI", 100, PURPLE), unsafe_allow_html=True)
k2.markdown(kpi_card("Positive", str(counts["positive"]), "good reviews", pct["positive"], GREEN), unsafe_allow_html=True)
k3.markdown(kpi_card("Neutral", str(counts["neutral"]), "mixed reviews", pct["neutral"], YELLOW), unsafe_allow_html=True)
k4.markdown(kpi_card("Negative", str(counts["negative"]), "bad reviews", pct["negative"], RED), unsafe_allow_html=True)

st.write("")

# ---------- Row 1: over time + topics ----------
left, right = st.columns([1.7, 1])
with left:
    with st.container(key="card_time"):
        if df["date"].notna().any():
            h1, h2 = st.columns([2, 1])
            h1.markdown('<div class="card-title">Timeline: reviews over time</div>', unsafe_allow_html=True)
            period = h2.radio("Group by", ["Day", "Week", "Month"], index=1, horizontal=True,
                              label_visibility="collapsed")
            freq = {"Day": "D", "Week": "W", "Month": "M"}[period]
            t = df.dropna(subset=["date"]).copy()
            t["period"] = t["date"].dt.to_period(freq).dt.start_time
            timeline = (t.groupby(["period", "sentiment"]).size()
                        .unstack(fill_value=0).reindex(columns=SENTIMENT_ORDER, fill_value=0))
            # Fill empty days/weeks/months with 0 so the lines don't skip them
            full = pd.period_range(t["date"].min(), t["date"].max(), freq=freq).start_time
            timeline = timeline.reindex(full, fill_value=0).rename_axis("period").reset_index()
            long = timeline.melt(id_vars="period", var_name="sentiment", value_name="reviews")
            fig = px.line(long, x="period", y="reviews", color="sentiment", markers=True,
                          color_discrete_map=SENTIMENT_COLORS, category_orders={"sentiment": SENTIMENT_ORDER})
            fig.update_traces(line=dict(width=3), marker=dict(size=7))
            fig.update_layout(xaxis_title=None, yaxis_title=f"Reviews per {period.lower()}", hovermode="x unified")
            fig.update_yaxes(rangemode="tozero", tickformat="d", dtick=1 if long["reviews"].max() <= 10 else None)
            fig.update_xaxes(tickformat={"Day": "%b %d", "Week": "%b %d", "Month": "%b %Y"}[period],
                             dtick="M1" if period == "Month" else None)
            st.plotly_chart(style_fig(fig), width="stretch")
        else:
            st.markdown('<div class="card-title">Sentiment by topic</div>', unsafe_allow_html=True)
            tp = df.groupby(["topic", "sentiment"]).size().reset_index(name="reviews")
            fig = px.bar(tp, x="topic", y="reviews", color="sentiment",
                         color_discrete_map=SENTIMENT_COLORS, category_orders={"sentiment": SENTIMENT_ORDER})
            fig.update_layout(barcornerradius=6, bargap=0.55, xaxis_title=None, yaxis_title="Reviews")
            st.plotly_chart(style_fig(fig), width="stretch")

with right:
    with st.container(key="card_topics"):
        st.markdown('<div class="card-title">Topics</div>', unsafe_allow_html=True)
        rows = ""
        top_n = df["topic"].value_counts().max()
        for topic, n in df["topic"].value_counts().items():
            sub = df[df["topic"] == topic]["sentiment"].value_counts()
            segs = "".join(
                f'<div style="width:{100 * sub.get(s, 0) / top_n:.1f}%;'
                f'background:{SENTIMENT_COLORS[s]}"></div>' for s in SENTIMENT_ORDER)
            rows += (f'<div class="topic-row"><div class="topic-name">{topic}</div>'
                     f'<div class="topic-bar">{segs}</div><div class="topic-count">{n}</div></div>')
        legend = "".join(f'<span class="legend-dot" style="background:{SENTIMENT_COLORS[s]}"></span>{s.capitalize()}'
                         for s in SENTIMENT_ORDER)
        st.markdown(rows + f'<div style="font-size:0.8rem;color:#6B7280;margin-top:0.8rem">{legend}</div>',
                    unsafe_allow_html=True)

# ---------- Row 2: donut + top issues ----------
left, right = st.columns([1, 1.7])
with left:
    with st.container(key="card_donut"):
        st.markdown('<div class="card-title">Sentiment</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Pie(
            labels=[s.capitalize() for s in SENTIMENT_ORDER], values=[counts[s] for s in SENTIMENT_ORDER],
            hole=0.68, sort=False, marker=dict(colors=[SENTIMENT_COLORS[s] for s in SENTIMENT_ORDER],
                                                line=dict(color="#FFFFFF", width=3)),
            textinfo="none", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
        fig.add_annotation(text=f"<b>{pct['positive']:.0f}%</b><br><span style='font-size:12px'>positive</span>",
                           showarrow=False, font=dict(size=22, color=GREEN))
        st.plotly_chart(style_fig(fig, 300), width="stretch")

with right:
    with st.container(key="card_issues"):
        st.markdown('<div class="card-title">Top 3 issues</div>', unsafe_allow_html=True)
        st.caption(data.get("overall_summary", ""))
        cols = st.columns(3)
        for col, issue in zip(cols, data.get("top_issues", [])):
            col.markdown(f"""
            <div class="issue" style="padding-top:0.6rem">
              <div style="font-weight:700;color:#111827">{issue['issue']}</div>
              <div class="issue-mentions">{issue['mentions']} mentions</div>
              <div style="font-size:0.88rem;color:#4B5563;margin-bottom:0.6rem">{issue['summary']}</div>
              <div class="tip">💡 {issue['suggestion']}</div>
            </div>""", unsafe_allow_html=True)

# ---------- Table ----------
with st.container(key="card_table"):
    st.markdown('<div class="card-title">All reviews</div>', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    sel_sent = f1.multiselect("Sentiment", SENTIMENT_ORDER, default=SENTIMENT_ORDER)
    topics = sorted(df["topic"].unique())
    sel_topic = f2.multiselect("Topic", topics, default=topics)
    view = df[df["sentiment"].isin(sel_sent) & df["topic"].isin(sel_topic)].copy()
    view["date"] = view["date"].dt.date
    cols_out = [c for c in ["review_id", "date", "rating", "review_text", "sentiment", "topic"]
                if c in view.columns and view[c].notna().any()]
    view = view[cols_out]
    icon = {"positive": "🟢 positive", "neutral": "🟡 neutral", "negative": "🔴 negative"}
    shown = view.assign(sentiment=view["sentiment"].map(icon))
    st.dataframe(shown, width="stretch", hide_index=True,
                 column_config={"review_text": st.column_config.TextColumn("Review", width="large"),
                                "review_id": "ID", "date": "Date", "rating": "Rating",
                                "sentiment": "Sentiment", "topic": "Topic"})
    st.download_button("⬇️ Download results (CSV)", view.to_csv(index=False).encode("utf-8"),
                       "review_insights.csv", "text/csv", type="primary")
