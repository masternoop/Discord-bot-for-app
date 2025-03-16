from flask import Flask, render_template, jsonify
import mysql.connector

app = Flask(__name__)


db = mysql.connector.connect(
    host="localhost",
    user="botuser",
    password="nope",
    database="olympus_bot"
)
cursor = db.cursor(dictionary=True)  

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/stats")
def stats():
    db.reconnect()  
    
    cursor.execute("SELECT id, total_earnings FROM cartel_sessions WHERE end_time IS NULL LIMIT 1")
    session = cursor.fetchone()
    
    active_session = "Yes" if session else "No"
    current_earnings = session['total_earnings'] if session else 0

    cursor.execute("SELECT username, balance FROM player_money WHERE balance > 0")
    money_owed = cursor.fetchall()

    total_owed = sum(row["balance"] for row in money_owed)

    participants = []
    if session:
        
        cursor.execute("SELECT username FROM cartel_participants WHERE session_id = %s", (session['id'],))
        participants = cursor.fetchall()

    return jsonify({
        "active_session": active_session,
        "participants": [row["username"] for row in participants] if session else [],
        "money_owed": [{"player": row["username"], "amount": row["balance"]} for row in money_owed],
        "total_owed": total_owed
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
