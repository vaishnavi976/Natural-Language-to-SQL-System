import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

# 🔥 CONFIG
API_URL = "http://localhost:8000/chat"

st.set_page_config(
    page_title="AI Clinic Chatbot",
    page_icon="🧠",
    layout="wide"
)

# ── Header ─────────────────────────────────────────────
st.title("🧠 AI Clinic Analytics Chatbot")
st.markdown("Ask questions about clinic data in plain English")

# ── Sidebar ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("Backend API:")
    st.code(API_URL)

    st.markdown("---")
    st.markdown("### 💡 Example Questions")
    st.markdown("""
    - How many patients do we have?
    - Show revenue by doctor
    - Top 5 patients by spending
    - Appointments by status
    """)

# ── Input ──────────────────────────────────────────────
question = st.text_input("💬 Enter your question:")

if st.button("Ask") and question:

    with st.spinner("Thinking..."):

        try:
            response = requests.post(
                API_URL,
                json={"question": question},
                timeout=30
            )

            data = response.json()

        except Exception as e:
            st.error(f"❌ API Error: {e}")
            st.stop()

    # ── Show message ─────────────────────────────
    st.subheader("🧾 Response")
    st.write(data.get("message", ""))

    # ── Show SQL ────────────────────────────────
    if data.get("sql_query"):
        with st.expander("🧠 Generated SQL"):
            st.code(data["sql_query"], language="sql")

    # ── Show Table ──────────────────────────────
    if data.get("columns") and data.get("rows"):
        df = pd.DataFrame(data["rows"], columns=data["columns"])

        st.subheader("📊 Data")
        st.dataframe(df, use_container_width=True)

        st.markdown(f"**Rows returned:** {data.get('row_count')}")

    # ── Show Chart ──────────────────────────────
    if data.get("chart"):
        st.subheader("📈 Visualization")

        try:
            fig = go.Figure(data=data["chart"]["data"])
            fig.update_layout(data["chart"]["layout"])

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.warning(f"⚠️ Chart rendering failed: {e}")

    # ── Cache indicator ─────────────────────────
    if data.get("cached"):
        st.info("⚡ Response served from cache")

# ── Footer ─────────────────────────────────────
st.markdown("---")
st.markdown(
    "Built with ❤️ using FastAPI + Vanna + Groq + Streamlit"
)