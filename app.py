from flask import Flask, render_template, request, send_from_directory, session, redirect

import qrcode

import os

import uuid

import sqlite3

from datetime import datetime



app = Flask(__name__)

app.secret_key = "qr_tracker_secret_key"



QR_FOLDER = "static/qr"

DATABASE = "qr_tracker.db"



os.makedirs(QR_FOLDER, exist_ok=True)





# =========================

# DATABASE SETUP

# =========================

def init_db():



    conn = sqlite3.connect(DATABASE)



    conn.execute("""

        CREATE TABLE IF NOT EXISTS qr_codes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            qr_id TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,

            data TEXT NOT NULL,

            qr_image TEXT NOT NULL,

            created_at TEXT NOT NULL,

            track_count INTEGER DEFAULT 0

        )

    """)



    conn.execute("""

        CREATE TABLE IF NOT EXISTS scan_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            qr_id TEXT NOT NULL,

            scanned_at TEXT NOT NULL,

            ip_address TEXT,

            user_agent TEXT

        )

    """)



    conn.commit()

    conn.close()



init_db()

# =========================

# ADMIN LOGIN

# =========================

@app.route("/login", methods=["GET", "POST"])

def login():



    if request.method == "POST":



        username = request.form["username"]

        password = request.form["password"]



        if username == "admin" and password == "admin123":

            session["admin"] = True

            return redirect("/dashboard")



        return "Invalid Username or Password"



    return render_template("login.html")





# =========================

# LOGOUT

# =========================

@app.route("/logout")

def logout():



    session.pop("admin", None)



    return redirect("/login")





# =========================

# HOME PAGE

# =========================

@app.route("/")

def home():



    return render_template("index.html")





# =========================

# DASHBOARD

# =========================

@app.route("/dashboard")

def dashboard():



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT COUNT(*)

        FROM qr_codes

    """)



    total_qr = cursor.fetchone()[0]



    cursor = conn.execute("""

        SELECT COALESCE(SUM(track_count), 0)

        FROM qr_codes

    """)



    total_scans = cursor.fetchone()[0]



    today = datetime.now().strftime("%Y-%m-%d")



    cursor = conn.execute("""

        SELECT COUNT(*)

        FROM qr_codes

        WHERE created_at LIKE ?

    """, (today + "%",))



    today_qr = cursor.fetchone()[0]



    cursor = conn.execute("""

        SELECT COALESCE(SUM(track_count), 0)

        FROM qr_codes

        WHERE created_at LIKE ?

    """, (today + "%",))



    today_scans = cursor.fetchone()[0]

    cursor = conn.execute("""

        SELECT COUNT(*)

        FROM scan_logs

    """)



    total_scan_logs = cursor.fetchone()[0]

    conn.close()

    return render_template(

        "dashboard.html",

        total_qr=total_qr,

        total_scans=total_scans,

        today_qr=today_qr,

        today_scans=today_scans,

        total_scan_logs=total_scan_logs

    )



# =========================

# SCAN LOGS

# =========================

@app.route("/scan-logs")

def scan_logs():



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT id, qr_id, scanned_at, ip_address, user_agent

        FROM scan_logs

        ORDER BY id DESC

    """)



    scan_logs = cursor.fetchall()



    conn.close()



    return render_template(

        "scan_logs.html",

        scan_logs=scan_logs

    )

# =========================

# QR HISTORY

# =========================

@app.route("/history")

def history():



    if "admin" not in session:

        return redirect("/login")



    search = request.args.get("search", "").strip()



    conn = sqlite3.connect(DATABASE)



    if search:



        cursor = conn.execute("""

            SELECT qr_id, name, data, created_at, track_count

            FROM qr_codes

            WHERE qr_id LIKE ?

               OR name LIKE ?

               OR data LIKE ?

            ORDER BY id DESC

        """, (

            f"%{search}%",

            f"%{search}%",

            f"%{search}%"

        ))



    else:



        cursor = conn.execute("""

            SELECT qr_id, name, data, created_at, track_count

            FROM qr_codes

            ORDER BY id DESC

        """)



    qr_codes = cursor.fetchall()



    conn.close()



    return render_template(

        "history.html",

        qr_codes=qr_codes,

        search=search

    )





# =========================

# GENERATE QR CODE

# =========================

@app.route("/generate", methods=["POST"])

def generate():



    if "admin" not in session:

        return redirect("/login")



    name = request.form["name"]

    data = request.form["data"]



    qr_id = str(uuid.uuid4())[:8]



    BASE_URL = os.getenv("BASE_URL", "https://qr-code-tracker-ys4y.onrender.com")
    qr_url = f"{BASE_URL}/track/{qr_id}"



    qr = qrcode.make(qr_url)



    qr_path = f"{QR_FOLDER}/{qr_id}.png"



    qr.save(qr_path)



    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



    conn = sqlite3.connect(DATABASE)



    conn.execute("""

        INSERT INTO qr_codes

        (qr_id, name, data, qr_image, created_at, track_count)

        VALUES (?, ?, ?, ?, ?, ?)

    """, (

        qr_id,

        name,

        data,

        f"/static/qr/{qr_id}.png",

        created_at,

        0

    ))



    conn.commit()

    conn.close()



    return render_template(

        "result.html",

        name=name,

        data=data,

        qr_id=qr_id,

        qr_image=f"/static/qr/{qr_id}.png"

    )





# =========================

# TRACK QR CODE

# =========================

@app.route("/track/<qr_id>")

def track(qr_id):



    conn = sqlite3.connect(DATABASE)



    # Check QR

    cursor = conn.execute("""

        SELECT name, data, track_count

        FROM qr_codes

        WHERE qr_id = ?

    """, (qr_id,))



    qr = cursor.fetchone()



    if not qr:



        conn.close()



        return "QR Code Not Found", 404



    name, data, track_count = qr



    # Increase scan count

    conn.execute("""

        UPDATE qr_codes

        SET track_count = track_count + 1

        WHERE qr_id = ?

    """, (qr_id,))



    # Scan information

    scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



    ip_address = request.remote_addr



    user_agent = request.headers.get("User-Agent", "")



    # Save scan log

    conn.execute("""

        INSERT INTO scan_logs

        (qr_id, scanned_at, ip_address, user_agent)

        VALUES (?, ?, ?, ?)

    """, (

        qr_id,

        scanned_at,

        ip_address,

        user_agent

    ))



    conn.commit()



    # New scan count

    new_track_count = track_count + 1



    conn.close()



    return f"""

    <h1>QR Code Tracked Successfully</h1>



    <p><b>QR ID:</b> {qr_id}</p>



    <p><b>Name:</b> {name}</p>



    <p><b>Data:</b> {data}</p>



    <p><b>Total Scans:</b> {new_track_count}</p>



    <p><b>Scanned At:</b> {scanned_at}</p>

    """





# =========================

# VIEW QR CODE

# =========================

@app.route("/view/<qr_id>")

def view_qr(qr_id):



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT qr_id, name, data, qr_image, created_at, track_count

        FROM qr_codes

        WHERE qr_id = ?

    """, (qr_id,))



    qr = cursor.fetchone()



    conn.close()



    if not qr:

        return "QR Code Not Found", 404



    return render_template("view_qr.html", qr=qr)





# =========================

# DOWNLOAD QR CODE

# =========================

@app.route("/download/<qr_id>")

def download_qr(qr_id):



    if "admin" not in session:

        return redirect("/login")



    filename = f"{qr_id}.png"



    if not os.path.exists(os.path.join(QR_FOLDER, filename)):

        return "QR Code Not Found", 404



    return send_from_directory(

        QR_FOLDER,

        filename,

        as_attachment=True

    )





# =========================

# DELETE QR CODE

# =========================

@app.route("/delete/<qr_id>")

def delete_qr(qr_id):



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT qr_image

        FROM qr_codes

        WHERE qr_id = ?

    """, (qr_id,))



    qr = cursor.fetchone()



    if not qr:



        conn.close()



        return "QR Code Not Found", 404



    # Delete scan logs

    conn.execute("""

        DELETE FROM scan_logs

        WHERE qr_id = ?

    """, (qr_id,))



    # Delete QR

    conn.execute("""

        DELETE FROM qr_codes

        WHERE qr_id = ?

    """, (qr_id,))



    conn.commit()



    conn.close()



    filename = f"{qr_id}.png"



    file_path = os.path.join(QR_FOLDER, filename)



    if os.path.exists(file_path):

        os.remove(file_path)



    return redirect("/history")



# =========================

# RECENT SCANS

# =========================

@app.route("/recent-scans")

def recent_scans():



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT id, qr_id, scanned_at, ip_address, user_agent

        FROM scan_logs

        ORDER BY id DESC

        LIMIT 20

    """)



    recent_scans = cursor.fetchall()



    conn.close()



    return render_template(

        "recent_scans.html",

        recent_scans=recent_scans

    )

# =========================

# TODAY'S SCAN LOGS

# =========================

@app.route("/today-scans")

def today_scans():



    if "admin" not in session:

        return redirect("/login")



    today = datetime.now().strftime("%Y-%m-%d")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT id, qr_id, scanned_at, ip_address, user_agent

        FROM scan_logs

        WHERE scanned_at LIKE ?

        ORDER BY id DESC

    """, (today + "%",))



    today_scans = cursor.fetchall()



    conn.close()



    return render_template(

        "today_scans.html",

        today_scans=today_scans

    )

# =========================

# QR-WISE SCAN DETAILS

# =========================

@app.route("/qr-details/<qr_id>")

def qr_details(qr_id):



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT name, data, track_count

        FROM qr_codes

        WHERE qr_id = ?

    """, (qr_id,))



    qr = cursor.fetchone()



    if not qr:

        conn.close()

        return "QR Code Not Found", 404



    cursor = conn.execute("""

        SELECT id, scanned_at, ip_address, user_agent

        FROM scan_logs

        WHERE qr_id = ?

        ORDER BY id DESC

    """, (qr_id,))



    scan_details = cursor.fetchall()



    conn.close()



    return render_template(

        "qr_details.html",

        qr_id=qr_id,

        qr=qr,

        scan_details=scan_details

    )

# =========================

# DATE-WISE SCAN REPORT

# =========================

@app.route("/date-report", methods=["GET"])

def date_report():



    if "admin" not in session:

        return redirect("/login")



    selected_date = request.args.get(

        "date",

        datetime.now().strftime("%Y-%m-%d")

    )



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT id, qr_id, scanned_at, ip_address, user_agent

        FROM scan_logs

        WHERE scanned_at LIKE ?

        ORDER BY id DESC

    """, (selected_date + "%",))



    date_scans = cursor.fetchall()



    conn.close()



    return render_template(

        "date_report.html",

        selected_date=selected_date,

        date_scans=date_scans

    )

# =========================

# IP / DEVICE DETAILS

# =========================

@app.route("/device-details")

def device_details():



    if "admin" not in session:

        return redirect("/login")



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT

            ip_address,

            user_agent,

            COUNT(*) AS scan_count,

            MAX(scanned_at) AS last_scanned

        FROM scan_logs

        GROUP BY ip_address, user_agent

        ORDER BY last_scanned DESC

    """)



    devices = cursor.fetchall()



    conn.close()



    return render_template(

        "device_details.html",

        devices=devices

    )

# =========================

# EXPORT SCAN REPORT - EXCEL

# =========================

@app.route("/export-excel")

def export_excel():



    if "admin" not in session:

        return redirect("/login")



    from openpyxl import Workbook



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT id, qr_id, scanned_at, ip_address, user_agent

        FROM scan_logs

        ORDER BY id DESC

    """)



    logs = cursor.fetchall()



    conn.close()



    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Scan Report"



    sheet.append([

        "ID",

        "QR ID",

        "Scanned At",

        "IP Address",

        "Device / Browser"

    ])



    for log in logs:

        sheet.append(log)



    file_path = "scan_report.xlsx"



    workbook.save(file_path)



    return send_from_directory(

        ".",

        file_path,

        as_attachment=True

    )

# =========================

# EXPORT SCAN REPORT - PDF

# =========================

@app.route("/export-pdf")

def export_pdf():



    if "admin" not in session:

        return redirect("/login")



    from reportlab.lib import colors

    from reportlab.lib.pagesizes import A4, landscape

    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle



    conn = sqlite3.connect(DATABASE)



    cursor = conn.execute("""

        SELECT id, qr_id, scanned_at, ip_address, user_agent

        FROM scan_logs

        ORDER BY id DESC

    """)



    logs = cursor.fetchall()



    conn.close()



    file_path = "scan_report.pdf"



    document = SimpleDocTemplate(

        file_path,

        pagesize=landscape(A4)

    )



    data = [

        [

            "ID",

            "QR ID",

            "Scanned At",

            "IP Address",

            "Device / Browser"

        ]

    ]



    for log in logs:

        data.append(list(log))



    table = Table(data, repeatRows=1)



    table.setStyle(TableStyle([

        ("BACKGROUND", (0, 0), (-1, 0), colors.black),

        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, -1), 8),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

    ]))



    document.build([table])



    return send_from_directory(

        ".",

        file_path,

        as_attachment=True

    )

# =========================

# START APPLICATION

# =========================

if __name__ == "__main__":



    init_db()



    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
