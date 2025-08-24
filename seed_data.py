import sqlite3, datetime, random
conn = sqlite3.connect("triage_logs.db")
c = conn.cursor()
samples = [
    ("mental","I have been anxious about work", "","", "NEGATIVE", 0.45, "Try 5 min breathing", 0),
    ("mental","I feel a bit low but okay", "","", "POSITIVE", 0.62, "Walk for 10 minutes", 0),
    ("triage","Mild cough and fever", "Normal", "Likely viral; rest and hydrate", None, 0.0, "", 0),
    ("triage","Chest pain and sweating", "Emergency - go to hospital", "Call emergency services immediately", None, 0.0, "", 1)
]
for s in samples:
    c.execute('''
        INSERT INTO triage_logs (timestamp, mode, text, urgency, explanation, sentiment_label, sentiment_score, recommendation, flagged)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.datetime.utcnow().isoformat(), *s))
conn.commit()
print("Seeded.")
