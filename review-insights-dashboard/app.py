"""Review Insights Dashboard
Streamlit app that sends customer reviews to an n8n workflow.
n8n asks Google Gemini to tag each review (sentiment + topic) and to find the top 3 issues.
"""
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Review Insights Dashboard", page_icon="🐶", layout="wide")

SENTIMENT_COLORS = {"positive": "#2E9E5B", "neutral": "#9AA0A6", "negative": "#D64545"}
SENTIMENT_ORDER = ["positive", "neutral", "negative"]

# The n8n webhook URL lives in Streamlit "Secrets", never in the code.
WEBHOOK_URL = st.secrets.get("N8N_WEBHOOK_URL", "")


def find_text_column(df: pd.DataFrame) -> str:
    """Guess which column holds the review text."""
    for name in ["review_text", "review", "text", "comment", "comentario", "reseña", "resena"]:
        for col in df.columns:
            if col.strip().lower() == name:
                return col
    # Otherwise use the column with the longest text on average
    text_cols = df.select_dtypes(include="object").columns
    return max(text_cols, key=lambda c: df[c].astype(str).str.len().mean())


def call_n8n(reviews: list[dict]) -> dict:
    resp = requests.post(WEBHOOK_URL, json={"reviews": reviews}, timeout=180)
    resp.raise_for_status()
    return resp.json()


# ---------- Header ----------
st.title("🐶 Review Insights Dashboard")
st.caption("Upload customer reviews. AI (Google Gemini, via n8n) tags each one by sentiment and topic and finds the top 3 issues.")

if not WEBHOOK_URL:
    st.error("The n8n webhook URL is missing. Add N8N_WEBHOOK_URL in the app's Secrets.")
    st.stop()

# ---------- Input ----------
tab_csv, tab_text = st.tabs(["📄 Upload a CSV", "✍️ Paste reviews"])
reviews: list[dict] = []

with tab_csv:
    file = st.file_uploader("CSV file with one review per row", type=["csv"])
    if file is not None:
        df_in = pd.read_csv(file)
        text_col = find_text_column(df_in)
        id_col = "review_id" if "review_id" in df_in.columns else None
        st.write(f"Found **{len(df_in)}** reviews (text column: `{text_col}`)")
        st.dataframe(df_in.head(5), width="stretch", hide_index=True)
        for i, row in df_in.iterrows():
            text = str(row[text_col]).strip()
            if text and text.lower() != "nan":
                rid = str(row[id_col]) if id_col else f"R{i + 1:03d}"
                reviews.append({"review_id": rid, "review_text": text})

with tab_text:
    pasted = st.text_area("One review per line", height=200,
                          placeholder="The harness arrived late...\nMe encanta el color, muy buena calidad...")
    if pasted.strip() and not reviews:
        lines = [l.strip() for l in pasted.splitlines() if l.strip()]
        reviews = [{"review_id": f"R{i + 1:03d}", "review_text": l} for i, l in enumerate(lines)]

analyze = st.button("🔍 Analyze reviews", type="primary", disabled=not reviews)

if analyze:
    with st.spinner(f"Gemini is reading {len(reviews)} reviews... this can take up to a minute"):
        try:
            st.session_state["data"] = call_n8n(reviews)
        except requests.exceptions.Timeout:
            st.error("n8n took too long to answer. Please try again.")
        except Exception as e:
            st.error(f"Something went wrong calling n8n: {e}")

data = st.session_state.get("data")
if not data:
    st.info("Upload a CSV or paste some reviews, then click **Analyze reviews**.")
    st.stop()

# ---------- Results ----------
df = pd.DataFrame(data["results"])
df["topic"] = df["topic"].str.replace("_", " ").str.capitalize()
counts = data["sentiment_counts"]
total = data["total_reviews"]

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Reviews analyzed", total)
c2.metric("Positive", counts["positive"], f"{counts['positive'] / total:.0%}", delta_color="off")
c3.metric("Neutral", counts["neutral"], f"{counts['neutral'] / total:.0%}", delta_color="off")
c4.metric("Negative", counts["negative"], f"{counts['negative'] / total:.0%}", delta_color="off")

left, right = st.columns(2)
with left:
    st.subheader("Sentiment")
    pie_df = pd.DataFrame({"sentiment": SENTIMENT_ORDER, "reviews": [counts[s] for s in SENTIMENT_ORDER]})
    fig = px.pie(pie_df, names="sentiment", values="reviews", hole=0.45,
                 color="sentiment", color_discrete_map=SENTIMENT_COLORS)
    fig.update_traces(textinfo="label+percent", sort=False)
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Topics")
    topic_df = df.groupby(["topic", "sentiment"]).size().reset_index(name="reviews")
    order = df["topic"].value_counts().index.tolist()
    fig = px.bar(topic_df, x="reviews", y="topic", color="sentiment", orientation="h",
                 color_discrete_map=SENTIMENT_COLORS,
                 category_orders={"topic": order, "sentiment": SENTIMENT_ORDER})
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), yaxis_title=None,
                      xaxis_title="Number of reviews", legend_title=None)
    st.plotly_chart(fig, width="stretch")

st.subheader("🚨 Top 3 issues")
st.write(data.get("overall_summary", ""))
cols = st.columns(3)
for col, issue in zip(cols, data.get("top_issues", [])):
    with col:
        with st.container(border=True):
            st.markdown(f"**{issue['issue']}**")
            st.caption(f"Mentioned in {issue['mentions']} reviews")
            st.write(issue["summary"])
            st.markdown(f"💡 *{issue['suggestion']}*")

st.subheader("All reviews")
f1, f2 = st.columns(2)
sel_sent = f1.multiselect("Sentiment", SENTIMENT_ORDER, default=SENTIMENT_ORDER)
sel_topic = f2.multiselect("Topic", sorted(df["topic"].unique()), default=sorted(df["topic"].unique()))
view = df[df["sentiment"].isin(sel_sent) & df["topic"].isin(sel_topic)]
st.dataframe(view, width="stretch", hide_index=True,
             column_config={"review_text": st.column_config.TextColumn("Review", width="large")})
st.download_button("⬇️ Download results (CSV)", view.to_csv(index=False).encode("utf-8"),
                   "review_insights.csv", "text/csv")
