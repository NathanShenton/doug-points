from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="⭐ Points Tracker", page_icon="⭐", layout="centered")

# ---- Configure what points are worth ----
POUNDS_PER_POINT = 0.02  # e.g. 1 point = 2p  (change this)

DB_URL = st.secrets["SUPABASE_DB_URL"]
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
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
            dict(
                entry_date=entry_date,
                person=person,
                activity=activity,
                points=int(points),
                notes=notes
            )
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
    # Ensure correct dtype if empty / weird
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.date
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).astype(int)
    return df

def delete_entry(entry_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM points_log WHERE id=:id"), {"id": entry_id})

init_db()

st.title("⭐ Points Tracker")

# Quick buttons (mobile UX win)
st.subheader("Quick add")
quick = [("🦷 Teeth", 3), ("🧸 Tidy", 3), ("❤️ Kindness", 5),
         ("📚 Homework", 5), ("🌙 Bedtime win", 4), ("🤝 Helped", 4)]

cols = st.columns(3)
for i, (label, pts) in enumerate(quick):
    with cols[i % 3]:
        if st.button(f"{label} +{pts}", use_container_width=True):
            insert_entry(date.today(), "Dougie", label, pts, None)
            st.success(f"Logged: {label} (+{pts})")
            st.rerun()

st.divider()

# Manual add
with st.form("add_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        entry_date = st.date_input("Date", date.today())
    with c2:
        person = st.selectbox("Who?", ["Dougie", "Dad", "Both"])

    activity = st.text_input("Activity")
    points = st.slider("Points", 1, 10, 3)
    notes = st.text_input("Notes (optional)")

    if st.form_submit_button("Add points ⭐", use_container_width=True):
        if not activity.strip():
            st.error("Enter an activity")
        else:
            insert_entry(entry_date, person, activity.strip(), points, notes.strip() or None)
            st.success("Saved")
            st.rerun()

df = load_entries()

# ---- Totals + £ value ----
if df.empty:
    st.info("No entries yet — add your first one above.")
else:
    total_points = int(df["points"].sum())
    today_points = int(df[df["entry_date"] == date.today()]["points"].sum())
    total_value = total_points * POUNDS_PER_POINT

    c1, c2, c3 = st.columns(3)
    c1.metric("Total points", total_points)
    c2.metric("Points today", today_points)
    c3.metric("Worth (£)", f"£{total_value:,.2f}")

    st.divider()

    # ---- Spend points ----
    st.subheader("Spend points")
    st.caption("This logs a negative entry in the database so the history is always auditable.")

    with st.form("spend_form", clear_on_submit=True):
        s1, s2 = st.columns(2)
        with s1:
            spend_date = st.date_input("Spend date", date.today(), key="spend_date")
        with s2:
            spend_person = st.selectbox("Who is spending?", ["Dougie", "Dad", "Both"], key="spend_person")

        spend_reason = st.text_input("What did you spend them on?", placeholder="e.g. Sweeties, Toy, Extra screen time")
        spend_points = st.number_input("Points to spend", min_value=1, max_value=100000, value=10, step=1)
        spend_notes = st.text_input("Notes (optional)", key="spend_notes")

        if st.form_submit_button("Spend (subtract points) 💸", use_container_width=True):
            if not spend_reason.strip():
                st.error("Add what the points were spent on.")
            elif spend_points > total_points:
                st.error(f"Not enough points. Available: {total_points}")
            else:
                # Negative points entry
                insert_entry(
                    spend_date,
                    spend_person,
                    f"SPEND: {spend_reason.strip()}",
                    -int(spend_points),
                    spend_notes.strip() or None
                )
                st.success(f"Spent {spend_points} points.")
                st.rerun()

    st.divider()

    st.subheader("History")
    # Optional: make spends obvious
    df_view = df.copy()
    df_view["type"] = df_view["points"].apply(lambda x: "Spend" if x < 0 else "Earn")
    st.dataframe(df_view.drop(columns="id"), hide_index=True, use_container_width=True)

    with st.expander("Delete entry"):
        selected = st.selectbox("Select ID", df["id"].tolist())
        if st.button("Delete 🗑️", use_container_width=True):
            delete_entry(int(selected))
            st.rerun()
