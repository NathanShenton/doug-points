from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---------------------------
# Config
# ---------------------------
st.set_page_config(page_title="⭐ Dougie’s Points Bank", page_icon="⭐", layout="centered")

DEFAULT_PERSON = "Dougie"
POUNDS_PER_POINT = 0.10  # 1 point = 10p

PARENT_PIN = st.secrets.get("PARENT_PIN", None)

REWARDS = [
    {"name": "🍬 Sweeties", "cost": 5, "notes": "Pick one sweet"},
    {"name": "🎮 30 mins game time", "cost": 5, "notes": "Extra gaming time"},
    {"name": "📺 Movie night pick", "cost": 10, "notes": "You choose the film"},
    {"name": "🧸 New toy", "cost": 25, "notes": "New toy"},
]

QUICK_EARN = [
    ("🦷 Teeth", 3),
    ("🧸 Tidy toys", 3),
    ("❤️ Kindness", 5),
    ("📚 Homework", 5),
    ("🌙 Bedtime win", 4),
    ("🤝 Helped", 4),
]

# ---------------------------
# Styling
# ---------------------------
st.markdown("""
<style>
.block-container {max-width: 720px;}
.hero {padding:16px;border-radius:18px;background:linear-gradient(135deg,#ffeaa7,#74b9ff);}
.big {font-size:44px;font-weight:800}
.section {font-size:20px;font-weight:800;margin-top:12px}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Database
# ---------------------------
DB_URL = st.secrets["SUPABASE_DB_URL"]
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
    pool_size=1,
    max_overflow=0,
)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS points_log (
                id SERIAL PRIMARY KEY,
                entry_date DATE NOT NULL,
                person TEXT NOT NULL,
                activity TEXT NOT NULL,
                points INT NOT NULL,
                notes TEXT
            );
        """))

def insert_entry(entry_date, person, activity, points, notes=""):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO points_log (entry_date, person, activity, points, notes)
                VALUES (:entry_date, :person, :activity, :points, :notes)
            """),
            dict(entry_date=entry_date, person=person, activity=activity, points=int(points), notes=notes)
        )

def load_entries():
    with engine.begin() as conn:
        df = pd.read_sql(
            text("""
                SELECT id, entry_date, person, activity, points, notes
                FROM points_log
                ORDER BY entry_date DESC, id DESC
            """),
            conn
        )
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.date
        df["points"] = df["points"].astype(int)
    return df

def delete_entry(entry_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM points_log WHERE id=:id"), {"id": entry_id})

# ---------------------------
# Helpers
# ---------------------------
def totals(df):
    lifetime = int(df[df["points"] > 0]["points"].sum()) if not df.empty else 0
    spent = int(df[df["points"] < 0]["points"].sum()) if not df.empty else 0
    balance = lifetime + spent
    today = int(df[df["entry_date"] == date.today()]["points"].sum()) if not df.empty else 0
    return lifetime, balance, today

def require_pin(key):
    if not PARENT_PIN:
        return True
    pin = st.text_input("Parent PIN", type="password", key=key)
    return pin == str(PARENT_PIN)

# ---------------------------
# App
# ---------------------------
init_db()
df = load_entries()
lifetime, balance, today = totals(df)

st.title("⭐ Dougie’s Points Bank")

st.markdown(f"""
<div class="hero">
<div class="big">{balance} ⭐</div>
<b>Worth:</b> £{balance * POUNDS_PER_POINT:.2f}<br>
<b>Lifetime:</b> {lifetime} pts (£{lifetime * POUNDS_PER_POINT:.2f})<br>
<b>Today:</b> {today} pts
</div>
""", unsafe_allow_html=True)

st.divider()

# ---------------------------
# Quick earn
# ---------------------------
st.markdown("<div class='section'>✨ Quick Earn</div>", unsafe_allow_html=True)
cols = st.columns(3)
for i, (label, pts) in enumerate(QUICK_EARN):
    with cols[i % 3]:
        if st.button(f"{label} +{pts}", use_container_width=True):
            insert_entry(date.today(), DEFAULT_PERSON, label, pts)
            st.balloons()
            st.rerun()

# ---------------------------
# Rewards Shop
# ---------------------------
st.divider()
st.markdown("<div class='section'>🎁 Rewards Shop</div>", unsafe_allow_html=True)

for r in REWARDS:
    cols = st.columns([3,1])
    with cols[0]:
        st.markdown(f"**{r['name']}** — {r['cost']} pts")
    with cols[1]:
        if st.button("Buy", key=r["name"], disabled=balance < r["cost"], use_container_width=True):
            insert_entry(date.today(), DEFAULT_PERSON, f"SPEND: {r['name']}", -r["cost"])
            st.snow()
            st.rerun()

# ---------------------------
# Parent tools
# ---------------------------
st.divider()
with st.expander("🧰 Parent controls"):
    if require_pin("pin_admin"):
        with st.form("custom"):
            s1, s2 = st.columns(2)
            with s1:
                activity = st.text_input("Reason")
            with s2:
                points = st.number_input("Points (+/-)", value=10, step=1)

            if st.form_submit_button("Apply"):
                insert_entry(date.today(), DEFAULT_PERSON, activity.strip(), int(points))
                st.success("Applied")
                st.rerun()

        if not df.empty:
            del_id = st.selectbox("Delete entry ID", df["id"].tolist())
            if st.button("Delete"):
                delete_entry(int(del_id))
                st.success("Deleted")
                st.rerun()

# ---------------------------
# History
# ---------------------------
st.divider()
st.markdown("<div class='section'>📜 History</div>", unsafe_allow_html=True)

df = load_entries()
if not df.empty:
    df["type"] = df["points"].apply(lambda x: "💸 Spend" if x < 0 else "✨ Earn")
    st.dataframe(df[["entry_date","type","activity","points"]], hide_index=True, use_container_width=True)
else:
    st.info("No history yet.")
