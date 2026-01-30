from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---------------------------
# Config
# ---------------------------
st.set_page_config(page_title="⭐ Points Tracker", page_icon="⭐", layout="centered")

POUNDS_PER_POINT = 0.02  # 1 point = 2p (change to what you want)
DEFAULT_PERSON = "Dougie"

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

def insert_entry(entry_date, person, activity, points, notes):
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
                "notes": notes
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

# ---------------------------
# App
# ---------------------------
init_db()
st.title("⭐ Points Tracker")
st.caption(f"Value rate: £{POUNDS_PER_POINT:.10f} per point")

df = load_entries()

# ---- Totals (Balance vs Lifetime) ----
if df.empty:
    balance_points = 0
    lifetime_points = 0
    today_points = 0
else:
    lifetime_points = int(df.loc[df["points"] > 0, "points"].sum())               # never decreases
    spent_points = int(df.loc[df["points"] < 0, "points"].sum())                  # negative
    balance_points = lifetime_points + spent_points                               # what can be spent
    today_points = int(df.loc[df["entry_date"] == date.today(), "points"].sum())  # includes spends if today

balance_value = balance_points * POUNDS_PER_POINT
lifetime_value = lifetime_points * POUNDS_PER_POINT

c1, c2 = st.columns(2)
c1.metric("Balance points", balance_points)
c2.metric("Points today", today_points)

c3, c4 = st.columns(2)
c3.metric("Worth (£) balance", f"£{balance_value:,.2f}")
c4.metric("Worth (£) lifetime", f"£{lifetime_value:,.2f}")

st.divider()

# ---------------------------
# Quick add (earn)
# ---------------------------
st.subheader("Quick add")
quick = [
    ("🦷 Teeth", 3),
    ("🧸 Tidy toys", 3),
    ("❤️ Kindness", 5),
    ("📚 Homework", 5),
    ("🌙 Bedtime win", 4),
    ("🤝 Helped", 4),
]
cols = st.columns(3)
for i, (label, pts) in enumerate(quick):
    with cols[i % 3]:
        if st.button(f"{label} +{pts}", use_container_width=True):
            insert_entry(date.today(), DEFAULT_PERSON, label, pts, "")
            st.success(f"Logged: {label} (+{pts})")
            st.rerun()

st.divider()

# ---------------------------
# Add earn entry (manual)
# ---------------------------
st.subheader("Add points")
with st.form("earn_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        entry_date = st.date_input("Date", date.today(), key="earn_date")
    with c2:
        person = st.selectbox("Who?", [DEFAULT_PERSON, "Dad", "Both"], key="earn_person")

    activity = st.text_input("Activity", placeholder="What happened?")
    points = st.slider("Points", 1, 10, 3)
    notes = st.text_input("Notes (optional)")

    if st.form_submit_button("Add points ⭐", use_container_width=True):
        if not activity.strip():
            st.error("Enter an activity")
        else:
            insert_entry(entry_date, person, activity.strip(), int(points), notes.strip() or "")
            st.success("Saved")
            st.rerun()

st.divider()

# ---------------------------
# Spend points (adds negative row)
# ---------------------------
st.subheader("Spend points")
st.caption("Spending inserts a negative points row. Lifetime points never drop; balance does.")

with st.form("spend_form", clear_on_submit=True):
    s1, s2 = st.columns(2)
    with s1:
        spend_date = st.date_input("Spend date", date.today(), key="spend_date")
    with s2:
        spend_person = st.selectbox("Who is spending?", [DEFAULT_PERSON, "Dad", "Both"], key="spend_person")

    spend_reason = st.text_input("What are you spending on?", placeholder="e.g. Sweeties, Toy, Screen time")
    spend_points = st.number_input("Points to spend", min_value=1, value=10, step=1)
    spend_notes = st.text_input("Notes (optional)", key="spend_notes")

    if st.form_submit_button("Spend (subtract) 💸", use_container_width=True):
        if not spend_reason.strip():
            st.error("Enter what the points were spent on")
        elif int(spend_points) > balance_points:
            st.error(f"Not enough points. Balance is {balance_points}.")
        else:
            insert_entry(
                spend_date,
                spend_person,
                f"SPEND: {spend_reason.strip()}",
                -int(spend_points),
                spend_notes.strip() or ""
            )
            st.success(f"Spent {int(spend_points)} points.")
            st.rerun()

st.divider()

# ---------------------------
# History
# ---------------------------
st.subheader("History")

df = load_entries()
if df.empty:
    st.info("No history yet.")
else:
    df_view = df.copy()
    df_view["type"] = df_view["points"].apply(lambda x: "Spend" if x < 0 else "Earn")
    df_view = df_view[["entry_date", "person", "type", "activity", "points", "notes"]]
    st.dataframe(df_view, hide_index=True, use_container_width=True)

    with st.expander("Delete entry (admin)"):
        selected = st.selectbox("Select entry ID", df["id"].tolist())
        if st.button("Delete 🗑️", use_container_width=True):
            delete_entry(int(selected))
            st.success("Deleted.")
            st.rerun()
