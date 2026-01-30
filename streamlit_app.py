from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="⭐ Points Tracker", page_icon="⭐", layout="centered")

DB_URL = st.secrets["SUPABASE_DB_URL"]
engine = create_engine(DB_URL, pool_pre_ping=True)

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
            dict(entry_date=entry_date, person=person,
                 activity=activity, points=points, notes=notes)
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
            st.success(f"{label} +{pts}")
            st.rerun()

st.divider()

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
            insert_entry(entry_date, person, activity, points, notes)
            st.success("Saved")
            st.rerun()

df = load_entries()

if not df.empty:
    c1, c2 = st.columns(2)
    c1.metric("Total points", int(df["points"].sum()))
    c2.metric("Points today", int(df[df["entry_date"] == date.today()]["points"].sum()))

    st.subheader("History")
    st.dataframe(df.drop(columns="id"), hide_index=True, use_container_width=True)

    with st.expander("Delete entry"):
        selected = st.selectbox("Select ID", df["id"].tolist())
        if st.button("Delete 🗑️", use_container_width=True):
            delete_entry(int(selected))
            st.rerun()
