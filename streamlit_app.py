from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ============================================================
# ⭐ Dougie's Points Bank — fun mobile-first Streamlit app
# Persistent storage: Supabase Postgres (pooler)
# ============================================================

# ---------------------------
# Page + game settings
# ---------------------------
st.set_page_config(page_title="⭐ Dougie’s Points Bank", page_icon="⭐", layout="centered")

DEFAULT_PERSON = "Dougie"

# Money conversion (optional “worth” display)
POUNDS_PER_POINT = 0.10  # 1 point = 10p (change to 0.02 if you want 2p)

# Parent PIN in Streamlit Secrets:
# PARENT_PIN="1234"
PARENT_PIN = st.secrets.get("PARENT_PIN", None)

# Rewards (you can edit these)
REWARDS = [
    {"name": "🍬 Sweeties", "cost": 5, "notes": "Pick one sweet"},
    {"name": "🎮 30 mins game time", "cost": 5, "notes": "Extra game time"},
    {"name": "📺 Movie night pick", "cost": 10, "notes": "You choose the film"},
    {"name": "🧸 New toy", "cost": 25, "notes": "A new toy"},
]

# Quick earn buttons (kid-friendly)
QUICK_EARN = [
    ("🦷 Teeth", 2),
    ("🧸 Tidy toys", 3),
    ("❤️ Kindness", 2),
    ("📚 Homework", 3),
    ("🌙 Bedtime win", 4),
    ("🤝 Helped", 2),
    ("👕 Changed Clothes", 2),
]

# ---------------------------
# Styling (simple + bright)
# ---------------------------
st.markdown("""
<style>
.block-container {max-width: 760px; padding-top: 1.1rem;}
.hero {
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,0.18);
  background: linear-gradient(135deg, rgba(255,215,0,0.22), rgba(0,180,255,0.14));
  box-shadow: 0 8px 22px rgba(0,0,0,0.18);
}
.hero-title {font-size: 18px; font-weight: 800; opacity: 0.95;}
.hero-big {font-size: 52px; font-weight: 900; line-height: 1; margin: 6px 0;}
.pills {margin-top: 8px;}
.pill {
  display:inline-block; padding: 6px 10px; border-radius: 999px;
  background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.16);
  margin-right: 8px; margin-top: 8px;
  font-weight: 600;
}
.section {font-size: 20px; font-weight: 900; margin-top: 6px;}
.subtle {opacity: 0.85;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# Database (Supabase via Secrets)
# ============================================================
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
            {
                "entry_date": entry_date,
                "person": person,
                "activity": activity,
                "points": int(points),
                "notes": notes or ""
            }
        )

def load_entries() -> pd.DataFrame:
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
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).astype(int)
        df["notes"] = df["notes"].fillna("")
    return df

def delete_entry(entry_id: int):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM points_log WHERE id = :id"), {"id": entry_id})

# ============================================================
# Helpers
# ============================================================
def pounds(points: int) -> float:
    return points * POUNDS_PER_POINT

def calc_totals(df: pd.DataFrame):
    """Lifetime ignores spends. Balance includes spends."""
    if df.empty:
        lifetime = 0
        spent = 0
        today = 0
    else:
        lifetime = int(df.loc[df["points"] > 0, "points"].sum())
        spent = int(df.loc[df["points"] < 0, "points"].sum())  # negative
        today = int(df.loc[df["entry_date"] == date.today(), "points"].sum())
    balance = lifetime + spent
    return lifetime, balance, today

def get_next_reward(balance_points: int):
    upcoming = sorted([r for r in REWARDS if r["cost"] > balance_points], key=lambda x: x["cost"])
    return upcoming[0] if upcoming else None

def require_pin(widget_key: str) -> bool:
    """
    Parent gate:
    - If PARENT_PIN not set in secrets: allow (no gate).
    - If set: require correct PIN (unique key per usage).
    """
    if not PARENT_PIN:
        st.info("Tip: set PARENT_PIN in Streamlit Secrets to lock parent-only actions.")
        return True
    pin = st.text_input("Parent PIN", type="password", key=widget_key)
    return pin == str(PARENT_PIN)

# ============================================================
# App
# ============================================================
init_db()

df = load_entries()
lifetime_points, balance_points, today_points = calc_totals(df)
next_reward = get_next_reward(balance_points)

st.markdown(f"## ⭐ {DEFAULT_PERSON}’s Points Bank")

# Hero card
st.markdown(f"""
<div class="hero">
  <div class="hero-title">Your balance</div>
  <div class="hero-big">{balance_points} ⭐</div>
  <div class="subtle">Worth about <b>£{pounds(balance_points):.2f}</b></div>
  <div class="pills">
    <span class="pill">🧠 Lifetime: {lifetime_points} pts (£{pounds(lifetime_points):.2f})</span>
    <span class="pill">📅 Today: {today_points} pts</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Progress to next reward
if next_reward:
    need = next_reward["cost"] - balance_points
    progress = min(balance_points / next_reward["cost"], 1.0)
    st.markdown(f"<div class='section'>🎯 Next reward: {next_reward['name']} ({next_reward['cost']} pts)</div>", unsafe_allow_html=True)
    st.progress(progress)
    st.caption(f"Only {need} points to unlock it!")
else:
    st.markdown("<div class='section'>🏆 Everything is unlocked!</div>", unsafe_allow_html=True)

st.divider()

# ---------------------------
# Quick Earn
# ---------------------------
st.markdown("<div class='section'>✨ Quick Earn</div>", unsafe_allow_html=True)

cols = st.columns(3)
for i, (label, pts) in enumerate(QUICK_EARN):
    with cols[i % 3]:
        if st.button(f"{label} +{pts}", key=f"earn_{label}", use_container_width=True):
            insert_entry(date.today(), DEFAULT_PERSON, label, pts, "")
            st.balloons()
            st.success(f"Nice one! {label} (+{pts})")
            st.rerun()

# Optional custom earn (parent can use too)
with st.expander("➕ Add custom points"):
    with st.form("earn_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            entry_date = st.date_input("Date", date.today(), key="earn_date")
        with c2:
            person = st.selectbox("Who?", [DEFAULT_PERSON, "Dad", "Both"], key="earn_person")
        activity = st.text_input("Activity", placeholder="What happened?")
        points = st.slider("Points", 1, 25, 5)
        notes = st.text_input("Notes (optional)")

        if st.form_submit_button("Add ⭐", use_container_width=True):
            if not activity.strip():
                st.error("Enter an activity")
            else:
                insert_entry(entry_date, person, activity.strip(), int(points), notes.strip())
                st.balloons()
                st.success("Saved!")
                st.rerun()

st.divider()

# ---------------------------
# Rewards Shop (spend)
# ---------------------------
st.markdown("<div class='section'>🎁 Rewards Shop</div>", unsafe_allow_html=True)
st.caption("Tap a reward to spend points. Spending adds a negative entry, so the history stays fair.")

for r in REWARDS:
    can_buy = balance_points >= r["cost"]
    cols = st.columns([3, 1])
    with cols[0]:
        st.markdown(f"**{r['name']}**  \n{r['notes']}  \nCost: **{r['cost']}** points")
    with cols[1]:
        if st.button("Buy ✅" if can_buy else "Locked 🔒", key=f"buy_{r['name']}", disabled=not can_buy, use_container_width=True):
            insert_entry(date.today(), DEFAULT_PERSON, f"SPEND: {r['name']}", -int(r["cost"]), r.get("notes", ""))
            st.snow()
            st.success(f"Bought: {r['name']} (-{r['cost']})")
            st.rerun()

# Parent-only custom spend (optional)
with st.expander("💸 Custom spend (Parent)"):
    if require_pin("pin_spend"):
        with st.form("spend_form", clear_on_submit=True):
            s1, s2 = st.columns(2)
            with s1:
                spend_date = st.date_input("Spend date", date.today(), key="spend_date")
            with s2:
                spend_person = st.selectbox("Who is spending?", [DEFAULT_PERSON, "Dad", "Both"], key="spend_person")

            spend_reason = st.text_input("What was it spent on?", placeholder="e.g. Big toy, Trip, etc.")
            spend_points = st.number_input("Points to spend", min_value=1, value=10, step=1)
            spend_notes = st.text_input("Notes (optional)", key="spend_notes")

            if st.form_submit_button("Spend 💸", use_container_width=True):
                if not spend_reason.strip():
                    st.error("Enter what it was spent on")
                elif int(spend_points) > balance_points:
                    st.error(f"Not enough points. Balance is {balance_points}.")
                else:
                    insert_entry(
                        spend_date,
                        spend_person,
                        f"SPEND: {spend_reason.strip()}",
                        -int(spend_points),
                        spend_notes.strip()
                    )
                    st.snow()
                    st.success("Spent!")
                    st.rerun()
    else:
        st.info("Enter the Parent PIN to unlock custom spending.")

st.divider()

# ---------------------------
# History
# ---------------------------
st.markdown("<div class='section'>📜 History</div>", unsafe_allow_html=True)

df = load_entries()
if df.empty:
    st.info("No history yet.")
else:
    df_view = df.copy()
    df_view["type"] = df_view["points"].apply(lambda x: "💸 Spend" if x < 0 else "✨ Earn")
    df_view = df_view[["entry_date", "type", "activity", "points", "notes"]]
    st.dataframe(df_view, hide_index=True, use_container_width=True)

# Parent-only delete
with st.expander("🧰 Admin (Parent) — delete entry"):
    if require_pin("pin_admin"):
        if df.empty:
            st.info("Nothing to delete.")
        else:
            selected = st.selectbox("Select entry ID", df["id"].tolist(), key="delete_id")
            if st.button("Delete 🗑️", use_container_width=True):
                delete_entry(int(selected))
                st.success("Deleted.")
                st.rerun()
    else:
        st.info("Enter the Parent PIN to unlock deletion.")
