import streamlit as st
import sqlite3
import json
import os
import re
import datetime
import hashlib
import pandas as pd
from config import LOGGING_ENABLED, EMERGENCY_PATTERNS, DEFAULT_EMERGENCY_NUMBER, HELPLINES, GPT_MODEL
from dotenv import load_dotenv
load_dotenv()  # this will read your .env file

import os
import streamlit as st
from openai import OpenAI

# Try to import transformers; if not present inform user
try:
    from transformers import pipeline
    SENTIMENT_AVAILABLE = True
except Exception as e:
    SENTIMENT_AVAILABLE = False

# -----------------------
# Setup
# -----------------------
st.set_page_config(page_title="AI Health Assistant", page_icon="💊", layout="centered")
st.title("💊 AI Healthcare Triage & Mental-Health Companion")

# OpenAI API key: from environment or Streamlit secrets
OPENAI_KEY = os.environ.get("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")

# Initialize sentiment pipeline if available
if SENTIMENT_AVAILABLE:
    try:
        sentiment = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    except Exception as e:
        st.error("Could not load sentiment model locally. You can still run without sentiment graphs.")
        SENTIMENT_AVAILABLE = False

# -----------------------
# Database (SQLite) - simulate cloud storage
# -----------------------
DB_PATH = "triage_logs.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS triage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    mode TEXT,
    text TEXT,
    urgency TEXT,
    explanation TEXT,
    sentiment_label TEXT,
    sentiment_score REAL,
    recommendation TEXT,
    flagged INTEGER
)
''')
conn.commit()

# -----------------------
# Helpers
# -----------------------
def extract_json_from_text(text):
    """Find a JSON object inside text and parse it."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except Exception:
        return None
from dotenv import load_dotenv
import os
import streamlit as st
from openai import OpenAI

# Load .env file
load_dotenv()

# Get the key
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Debug check
print("API Key Loaded:", OPENAI_KEY[:8] + "..." if OPENAI_KEY else "Not Found")

# Initialize client
client = OpenAI(api_key=OPENAI_KEY)

def call_gpt5_system(prompt, max_tokens=200, temperature=0.2):
    """Call OpenAI Chat Completions API (new client)."""
    try:
        resp = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "You are a concise, careful medical/mental health assistant. Provide brief clear answers and DO NOT invent contact numbers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"OpenAI call failed: {e}")
        return None


def check_emergency_regex(text):
    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return True
    return False

def anonymize_text(text):
    # Basic hashing to keep logs non-identifiable if LOGGING_ENABLED True
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def save_log(mode, text, urgency="", explanation="", sentiment_label=None, sentiment_score=None, recommendation="", flagged=0):
    stored_text = anonymize_text(text) if LOGGING_ENABLED else ""
    c.execute('''
        INSERT INTO triage_logs (timestamp, mode, text, urgency, explanation, sentiment_label, sentiment_score, recommendation, flagged)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.datetime.utcnow().isoformat(), mode, stored_text, urgency, explanation, sentiment_label, sentiment_score, recommendation, int(flagged)))
    conn.commit()

# -----------------------
# UI: Sidebar + Modes
# -----------------------
mode = st.sidebar.selectbox("Mode", ["Symptom Triage", "Mental Health Check-in", "Community Dashboard", "Settings"])

if mode == "Settings":
    st.header("Settings & Data Privacy")
    st.write("""
    - **Logging enabled:** `{}` (change in config.py)
    - **Emergency number:** {}
    """.format(LOGGING_ENABLED, DEFAULT_EMERGENCY_NUMBER))
    st.markdown("**Privacy notes**: This demo is *not* a medical device. Do not store raw personal data in logs for production; anonymize or encrypt. See README for GDPR guidance.")
    st.stop()

# -----------------------
# Mode: Symptom Triage
# -----------------------
if mode == "Symptom Triage":
    st.header("🩺 Symptom Triage")
    st.write("Describe symptoms. The assistant will classify urgency into: Normal / See Doctor Soon / Emergency — go to hospital.")
    symptoms = st.text_area("Symptoms", height=160, placeholder="e.g., 'Severe chest pain, shortness of breath for 30 minutes'...")
    if st.button("Analyze symptoms"):
        if not symptoms.strip():
            st.warning("Please enter symptoms.")
        else:
            # Emergency quick regex check
            if check_emergency_regex(symptoms):
                st.error("⚠️ Detected language suggesting immediate self-harm or severe crisis.")
                st.markdown(f"**If you are in immediate danger call {DEFAULT_EMERGENCY_NUMBER} or your local emergency number now.**")
                # save flagged log (do not store raw text if privacy concerns)
                save_log("triage", symptoms, urgency="Emergency (flagged)", explanation="Regex detected crisis", flagged=1)
            else:
                # Build a strict prompt asking for ONLY JSON
                prompt = f"""
                You are a medical triage assistant. Based on the symptoms below, respond ONLY with a JSON object (no extra text). JSON keys:
                {{
                  "urgency": one of ["Normal", "See Doctor Soon", "Emergency - go to hospital"],
                  "explanation": short patient-friendly explanation (max 80 words)
                }}
                Symptoms:
                \"\"\"{symptoms}\"\"\"
                """
                gresp = call_gpt5_system(prompt, max_tokens=240)
                if gresp:
                    parsed = extract_json_from_text(gresp)
                    if parsed:
                        urgency = parsed.get("urgency","Unclear")
                        explanation = parsed.get("explanation","")
                        st.subheader("Triage result")
                        if "Emergency" in urgency:
                            st.error(f"**{urgency}**")
                        elif "See Doctor" in urgency:
                            st.warning(f"**{urgency}**")
                        else:
                            st.success(f"**{urgency}**")
                        st.info(explanation)
                        save_log("triage", symptoms, urgency=urgency, explanation=explanation, flagged=(1 if "Emergency" in urgency else 0))
                    else:
                        st.error("Could not parse model response. Raw output shown:")
                        st.write(gresp)
                        save_log("triage", symptoms, urgency="ParsingFailed", explanation=gresp, flagged=0)

# -----------------------
# Mode: Mental Health Check-in
# -----------------------
elif mode == "Mental Health Check-in":
    st.header("💬 Mental Health Check-in")
    st.write("Write how you feel. The assistant gives a supportive reply, sentiment, micro-recommendations, and flags crisis language.")
    entry = st.text_area("How are you feeling today?", height=160, placeholder="e.g., 'I have been feeling very down and can't sleep...'")
    if st.button("Submit check-in"):
        if not entry.strip():
            st.warning("Please write something.")
        else:
            # Quick regex emergency check
            regex_flag = check_emergency_regex(entry)
            sentiment_label, sentiment_score = None, None
            if SENTIMENT_AVAILABLE:
                try:
                    s = sentiment(entry[:512])[0]
                    sentiment_label, sentiment_score = s["label"], float(s["score"])
                except Exception as e:
                    st.write("Sentiment model failed:", e)

            # Ask GPT for supportive reply & one micro-recommendation; require JSON output
            prompt = f"""
            You are a compassionate mental health support assistant. Given the user's text below, respond ONLY with JSON:
            {{
              "supportive_reply": "A brief empathetic reply (max 60 words)",
              "recommendation": "One small actionable micro-step the user can try now (max 20 words)",
              "emergency_flag": "yes" or "no"
            }}
            User text:
            \"\"\"{entry}\"\"\"
            Ensure you NEVER provide instructions for self-harm. If the content indicates suicide or intent to self-harm, set emergency_flag to \"yes\".
            """
            gresp = call_gpt5_system(prompt, max_tokens=220)
            parsed = extract_json_from_text(gresp) if gresp else None

            # Combine flags: regex OR model
            emergency_flag = False
            if parsed:
                emergency_flag = parsed.get("emergency_flag","no").strip().lower() == "yes"
                supportive = parsed.get("supportive_reply","")
                recommendation = parsed.get("recommendation","")
            else:
                supportive = "Thanks for sharing. It's okay to feel this way; consider reaching out to someone you trust."
                recommendation = "Try a 2-minute breathing exercise."
                parsed = {}
            if regex_flag:
                emergency_flag = True

            # If emergency -> immediate UI
            if emergency_flag:
                st.error("⚠️ This check-in appears to indicate a crisis.")
                st.markdown(f"**If you are in immediate danger call {DEFAULT_EMERGENCY_NUMBER} now.**")
                st.markdown("If you are in Finland, call emergency number 112. Contact local crisis services immediately.")
                # show supportive text
                st.info(supportive)
            else:
                st.success("Supportive reply:")
                st.write(supportive)
                st.write("Recommendation:", recommendation)

            # Save log (anonymized optionally)
            save_log("mental", entry, urgency="", explanation=supportive, sentiment_label=sentiment_label, sentiment_score=(sentiment_score if sentiment_score else 0.0), recommendation=recommendation, flagged=(1 if emergency_flag else 0))

# -----------------------
# Mode: Community Dashboard
# -----------------------
elif mode == "Community Dashboard":
    st.header("📈 Community Wellbeing Dashboard")
    st.write("Aggregated (anonymized) trends from recent check-ins (demo data).")

    df = pd.read_sql_query("SELECT timestamp, mode, sentiment_label, sentiment_score, flagged FROM triage_logs ORDER BY id DESC LIMIT 200", conn)
    if df.empty:
        st.info("No logs yet. Use Symptom Triage or Mental Health modes to generate sample data.")
    else:
        # Convert timestamps
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # Show last 20 records
        st.subheader("Recent anonymized logs (last 20)")
        st.dataframe(df.head(20))

        # Compute simple wellbeing index: average sentiment_score for mental mode
        mental_df = df[df["mode"] == "mental"]
        if not mental_df.empty:
            # sentiment_score is between 0..1 and label POSITIVE/NEGATIVE
            # map to -1..1: positive -> +score, negative -> -score
            def map_score(row):
                if row["sentiment_label"] is None:
                    return 0.0
                if row["sentiment_label"].upper().startswith("POS"):
                    return float(row["sentiment_score"])
                else:
                    return -float(row["sentiment_score"])
            mental_df["well_score"] = mental_df.apply(map_score, axis=1)
            # rolling average by time
            series = mental_df.set_index("timestamp").resample("1D")["well_score"].mean().fillna(method="ffill").fillna(0)
            st.subheader("Wellbeing trend (daily average)")
            st.line_chart(series)
            pct_flagged = (mental_df["flagged"].sum() / len(mental_df)) * 100
            st.metric("Flagged as crisis", f"{pct_flagged:.1f}%")
        else:
            st.info("No mental health check-ins yet to compute trends.")
