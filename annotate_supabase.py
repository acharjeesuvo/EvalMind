import streamlit as st
import pandas as pd
import psycopg2
import bcrypt
import datetime
import os
from PIL import Image

# PostgreSQL Configuration
PG_CONFIG = {
    "dbname": st.secrets["dbname"],
    "user": st.secrets["user"],
    "password": st.secrets["password"],
    "host": st.secrets["host"],
    "port": st.secrets["port"]

}

# DB Connection

def get_db_connection():
    return psycopg2.connect(**PG_CONFIG)

# Log login time
def log_login_time(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO login_log (user_id, login_time) VALUES (%s, %s)", (user_id, datetime.datetime.now()))
    conn.commit()
    cur.close()
    conn.close()

# Get next unannotated image
def get_next_image(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.image_name, i.tweet_text, i.llm_reasoning FROM input_data i
        WHERE i.image_name NOT IN (
            SELECT image_name FROM annotated WHERE user_id = %s
        )
        ORDER BY i.image_name
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

# Save annotation
def save_annotation(user_id, image_name, evidence, reasoning, naturalness, accept_status):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM annotated WHERE user_id = %s AND image_name = %s", (user_id, image_name))
    cur.execute("""
        INSERT INTO annotated (user_id, image_name, evidence_recognition, reasoning_chain, text_naturalness, accept_status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, image_name, evidence, reasoning, naturalness, accept_status))
    conn.commit()
    cur.close()
    conn.close()

# Get progress
def get_progress(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM input_data")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM annotated WHERE user_id = %s", (user_id,))
    done = cur.fetchone()[0]
    cur.close()
    conn.close()
    return done, total

# Login UI
def login_ui():
    st.title("🔐 Login to Annotation Tool")
    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password, COALESCE(role, 'annotator') FROM user_data WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            stored_password, role = result
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                if role != 'annotator':
                    st.error("🚫 Access denied: This account does not have annotator privileges.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    log_login_time(user_id)
                    st.rerun()
            else:
                st.error("❌ Incorrect password.")
        else:
            st.error("❌ User ID not found.")
        st.stop()

# Review Mode
def review_mode():
    st.success("✅ All annotations done!")

# Main app logic
def main():
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        login_ui()
        return  # Prevent further code from running if not logged in



    user_id = st.session_state.user_id
    st.sidebar.title("👤 Annotator Panel")
    st.sidebar.write(f"User: `{user_id}`")
    if st.sidebar.button("🔓 Logout"):
        st.session_state.clear()
        st.rerun()

    done, total = get_progress(user_id)
    st.sidebar.markdown(f"**Progress:** {done} / {total}")
    st.sidebar.progress(done / total if total > 0 else 0)

    row = get_next_image(user_id)
    if not row:
        review_mode()
        return

    image_name, tweet_text, llm_reasoning = row
    st.header("🖼️ Image Annotation")
    image_path = os.path.join("images", image_name)
    if os.path.exists(image_path):
        st.image(image_path, width=400)
    else:
        st.error(f"Image not found: {image_name}")

    st.markdown(f"**Tweet Text:** {tweet_text}")
    st.markdown(f"**LLM Reasoning:** {llm_reasoning}")

    st.subheader("🔎 Your Evaluation")
    evidence = st.slider("Evidence Recognition", 1, 5, 3)
    reasoning = st.slider("Reasoning Chain", 1, 5, 3)
    naturalness = st.slider("Text Naturalness", 1, 5, 3)
    accept_status = 1 if st.radio("Accept this reasoning?", ["Yes", "No"]) == "Yes" else 0

    if st.button("✅ Submit Annotation"):
        save_annotation(user_id, image_name, evidence, reasoning, naturalness, accept_status)
        st.success("Annotation submitted!")
        st.rerun()

if __name__ == "__main__":
    main()
