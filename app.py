from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from model import ParkEaseModel
import random
import smtplib
from email.mime.text import MIMEText
import threading
import sqlite3
import razorpay
import os
from datetime import datetime, timedelta
import socket

app = Flask(__name__)
app.config['SECRET_KEY'] = 'parkease_secret_key_123'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Razorpay Config (Replace with your actual keys from Razorpay Dashboard)
RAZORPAY_KEY_ID = "rzp_test_U66bQfXy8B9X6S" 
RAZORPAY_KEY_SECRET = "G7o8vH8W8X8Y8Z8A8B8C8D8E"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ---------------- Config ----------------
DB_FILE      = "users.db"
EMAIL        = "monamusmade25@gmail.com"
APP_PASSWORD = "effh qsrv wlzh bkdl" 
ADMIN_EMAIL  = "godreaishwarya@gmail.com"
GUARD_EMAIL  = "guard@parkease.com"


ml = ParkEaseModel()
try:
    ml.train_from_csv("nanded_parking_data (1).csv")
except Exception as e:
    print(f"ML Training Error: {e}")
slot_bookings = {}
otp_store = {}

# ============================================================
# DATABASE INIT
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Self-healing migration: Drop outdated bookings table if it is missing payment_status
    try:
        c.execute("SELECT payment_status FROM bookings LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("DROP TABLE IF EXISTS bookings")

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        message TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        slot_id TEXT,
        name TEXT,
        email TEXT,
        mobile TEXT,
        aadhar TEXT,
        vehicle TEXT,
        time TEXT,
        hours INTEGER,
        charge INTEGER,
        payment_status TEXT DEFAULT 'Pending',
        screenshot TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS guards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        area TEXT,
        shift TEXT
    )""")

    # Migration: Add columns independently to avoid skipping on errors
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN hours INTEGER")
    except: pass
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN charge INTEGER")
    except: pass
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN aadhar TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE guards ADD COLUMN shift TEXT")
    except: pass

    conn.commit()
    conn.close()
    
    if not os.path.exists("static/uploads"):
        os.makedirs("static/uploads")

init_db()

# ============================================================
# PAGES
# ============================================================

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/features")
def features():
    return render_template("features.html")

@app.route("/booking")
def booking():
    return render_template("booking.html") 

@app.route("/admin-login-page")
def admin_login_page():
    return render_template("admin_login.html")

@app.route("/guard-login-page")
def guard_login_page():
    return render_template("guard_login.html")

# ============================================================
# ADMIN
# ============================================================

@app.route("/admin")
def admin():
    users, messages, bookings, guards = [], [], [], []
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users")
        users = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM messages")
        messages = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM bookings")
        bookings = [dict(row) for row in cursor.fetchall()]
        
        try:
            cursor.execute("SELECT * FROM guards")
            guards = [dict(row) for row in cursor.fetchall()]
        except:
            pass # Table might not exist yet
            
        conn.close()
        
        # Calculate Analytics
        total_earnings = sum(b.get('charge', 0) for b in bookings if b.get('payment_status') == 'Verified')
        pending_payments = len([b for b in bookings if b.get('payment_status') == 'Pending'])
    except Exception as e:
        print(f"Admin Route Error: {e}")
        total_earnings, pending_payments = 0, 0
    
    return render_template("admin.html", 
                           users=users, 
                           messages=messages, 
                           bookings=bookings, 
                           guards=guards, 
                           locations=ml.LOCATIONS or {},
                           earnings=total_earnings,
                           pending=pending_payments)

@app.route("/admin/verify-payment/<int:id>/<string:status>", methods=["POST"])
def admin_verify_payment(id, status):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET payment_status=? WHERE id=?", (status, id))
    conn.commit()

    if status == "Verified":
        try:
            cursor.execute("SELECT * FROM bookings WHERE id=?", (id,))
            booking = cursor.fetchone()
            if booking:
                email = booking["email"]
                name = booking["name"]
                loc_key = booking["location"]
                slot_id = booking["slot_id"]
                vehicle = booking["vehicle"]
                b_time = booking["time"]
                hours = booking["hours"]
                charge = booking["charge"]
                
                # Fetch clean location name
                loc_name = ml.LOCATIONS.get(loc_key, {}).get("name", loc_key)
                
                subject = f"✅ Booking Confirmed — ID: PE-00{id}"
                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; color: #333; background-color: #f9f9f9; padding: 20px; line-height: 1.6;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border: 1px solid #e0e0e0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                        <div style="background: linear-gradient(135deg, #a855f7, #7c3aed); padding: 30px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 24px; font-weight: bold;">PARKEASE Smart Parking</h2>
                            <p style="margin: 5px 0 0 0; opacity: 0.8; font-size: 14px; letter-spacing: 1px;">OFFICIAL RECEIPT & CONFIRMATION</p>
                        </div>
                        <div style="padding: 30px;">
                            <p>Dear <strong>{name}</strong>,</p>
                            <p style="color: #4b5563;">Your parking payment has been verified by the administrator. Your slot is officially reserved.</p>
                            
                            <div style="background: #f3f4f6; border-radius: 12px; padding: 20px; margin: 20px 0;">
                                <h3 style="margin-top: 0; color: #7c3aed; font-size: 16px;">Parking Booking Receipt</h3>
                                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 8px 0; color: #6b7280;">Booking ID</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">PE-00{id}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 8px 0; color: #6b7280;">Location</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">{loc_name}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 8px 0; color: #6b7280;">Slot ID</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #a855f7;">{slot_id}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 8px 0; color: #6b7280;">Vehicle Number</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: bold; text-transform: uppercase;">{vehicle}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 8px 0; color: #6b7280;">Duration</td>
                                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">{hours} Hour(s)</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 8px 0; color: #6b7280;">Booking Time</td>
                                        <td style="padding: 8px 0; text-align: right;">{b_time}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 12px 0 0 0; color: #111827; font-weight: bold; font-size: 16px;">Total Paid</td>
                                        <td style="padding: 12px 0 0 0; text-align: right; font-weight: bold; font-size: 20px; color: #10b981;">₹{charge}</td>
                                    </tr>
                                </table>
                            </div>
                            
                            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 12px; text-align: center; color: #065f46; font-weight: bold; font-size: 14px; margin-bottom: 20px;">
                                Status: VERIFIED & PAID ✅
                            </div>

                            <p style="font-size: 12px; color: #9ca3af; text-align: center;">Please keep this email as confirmation for entry. For support, contact us through our website.</p>
                            <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 25px 0;">
                            <p style="font-size: 11px; text-align: center; color: #9ca3af; margin: 0;">ParkEase Administration | Nanded Smart Parking</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                # Send email using background thread so UI stays lightning-fast
                threading.Thread(target=send_email, args=(email, subject, html_body)).start()
        except Exception as e:
            print(f"Receipt email error: {e}")

    conn.close()
    return jsonify({"success": True})

@app.route("/admin/delete-booking/<int:id>", methods=["POST"])
def admin_delete_booking(id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/admin/delete-user/<int:id>", methods=["POST"])
def admin_delete_user(id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/admin/delete-message/<int:id>", methods=["POST"])
def admin_delete_message(id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ============================================================
# OTP SYSTEM
# ============================================================

def send_email(to_email, subject, body):
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = to_email

    try:
        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(EMAIL, APP_PASSWORD)
        s.sendmail(EMAIL, to_email, msg.as_string())
        s.quit()
    except Exception as e:
        print("Email error:", e)

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data.get("email")
    name = data.get("name", "User")
    otp = str(random.randint(100000, 999999))

    otp_store[email] = otp
    
    subject = "ParkEase Smart Parking, Nanded"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #202124; font-size: 14px;">
        <h2 style="margin-bottom: 20px; font-size: 20px;">ParkEase Smart Parking, Nanded</h2>
        <p style="margin-bottom: 20px;">Dear <b>{name}</b>,</p>
        <p style="margin-bottom: 20px;">Your ParkEase OTP is:</p>
        <p style="color: #1a73e8; font-weight: bold; font-size: 16px; margin-bottom: 20px;">{otp}</p>
        <p style="margin-bottom: 20px;"><b>Email Address:</b> {email}</p>
        <p style="margin-bottom: 20px;">Please enter this OTP to verify your account immediately.</p>
        <p style="margin-bottom: 40px;"><b>Note:</b> Do not share your OTP with anyone.</p>
        <p style="margin-bottom: 4px;">Regards,</p>
        <p style="margin-top: 0;"><b>ParkEase Smart Parking Team</b></p>
    </body>
    </html>
    """
    
    threading.Thread(target=send_email, args=(email, subject, html_body)).start()
    return jsonify({"success": True})

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    if email in otp_store and otp_store[email] == otp:
        del otp_store[email]
        return jsonify({"success": True})

    return jsonify({"success": False})

# ============================================================
# AUTH
# ============================================================

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users(name,email,password) VALUES(?,?,?)",
            (data.get("name"), data.get("email"), data.get("password"))
        )
        conn.commit()
        return jsonify({"success": True})
    except:
        return jsonify({"success": False, "message": "Email exists"})
    finally:
        conn.close()

@app.route("/login-user", methods=["POST"])
def login_user():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name,password FROM users WHERE email=?", (data.get("email"),))
    user = cursor.fetchone()
    conn.close()

    if user and user[1] == data.get("password"):
        return jsonify({"success": True, "name": user[0]})

    return jsonify({"success": False})

@app.route("/login-admin", methods=["POST"])
def login_admin():
    data = request.get_json()
    if data.get("email") == ADMIN_EMAIL and data.get("password") == "admin123":
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/login-guard", methods=["POST"])
def login_guard():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT area FROM guards WHERE email=? AND password=?", (email, password))
    guard = cursor.fetchone()
    conn.close()

    if guard:
        return jsonify({"success": True, "area": guard[0]})
    
    return jsonify({"success": False, "message": "Invalid credentials."})

def send_async_email(email_addr, name, guard_id, password, area, shift, base_url):
    try:
        from email.mime.multipart import MIMEMultipart
        joining_date = datetime.now().strftime("%B %d, %Y")
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "PARKEASE — Official Guard Appointment Letter"
        msg["From"] = EMAIL
        msg["To"] = email_addr

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #a855f7, #f472b6); padding: 20px; text-align: center;">
                    <h1 style="color: white; margin: 0;">PARKEASE NANDED</h1>
                    <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0 0; font-size: 12px; letter-spacing: 2px;">OFFICIAL APPOINTMENT</p>
                </div>
                <div style="padding: 30px;">
                    <p>Dear <strong>{name}</strong>,</p>
                    <p>Congratulations! You have been officially registered as a Security Guard for the ParkEase Smart Parking System in Nanded.</p>
                    
                    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #a855f7;">Assignment Details:</h3>
                        <p style="margin: 5px 0;"><strong>Joining Date:</strong> {joining_date}</p>
                        <p style="margin: 5px 0;"><strong>Assigned Area:</strong> {area.upper()}</p>
                        <p style="margin: 5px 0;"><strong>Assigned Shift:</strong> {shift}</p>
                    </div>

                    <div style="background: #fff5f7; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #fed7e7;">
                        <h3 style="margin-top: 0; color: #f472b6;">Login Credentials:</h3>
                        <p style="margin: 5px 0;"><strong>Email:</strong> {email_addr}</p>
                        <p style="margin: 5px 0;"><strong>Password:</strong> {password}</p>
                    </div>

                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{base_url}admin/view-joining-letter/{guard_id}" 
                           style="background: #a855f7; color: white; padding: 15px 25px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                           VIEW / DOWNLOAD OFFICIAL PDF LETTER
                        </a>
                    </p>

                    <p style="font-size: 12px; color: #666;">Note: Click the button above to view your official appointment letter. You can save it as a PDF or print it directly from your browser.</p>
                    
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 11px; text-align: center; color: #999;">ParkEase Administration | Nanded City Smart Parking</p>
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, APP_PASSWORD)
            server.sendmail(EMAIL, email_addr, msg.as_string())
    except Exception as email_err:
        print(f"Failed to send async joining letter: {email_err}")

@app.route("/admin/add-guard", methods=["POST"])
def add_guard():
    data = request.get_json()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO guards (name, email, password, area, shift) VALUES (?, ?, ?, ?, ?)",
                       (data.get("name"), data.get("email"), data.get("password"), data.get("area"), data.get("shift")))
        conn.commit()
        guard_id = cursor.lastrowid
        conn.close()

        # Determine the best URL for the email (Local IP is better for mobile access)
        base_url = request.host_url
        if "127.0.0.1" in base_url or "localhost" in base_url:
            local_ip = get_local_ip()
            base_url = f"http://{local_ip}:5000/"

        # Start background thread for email so UI stays FAST
        threading.Thread(target=send_async_email, args=(
            data.get("email"), data.get("name"), guard_id, 
            data.get("password"), data.get("area"), data.get("shift"),
            base_url
        )).start()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/admin/view-joining-letter/<int:id>")
def view_joining_letter(id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guards WHERE id=?", (id,))
    guard = cursor.fetchone()
    conn.close()
    
    if not guard:
        return "Guard record not found", 404
        
    joining_date = datetime.now().strftime("%B %d, %Y")
    return render_template("joining_letter.html", guard=guard, date=joining_date)

@app.route("/admin/delete-guard/<int:id>", methods=["POST"])
def delete_guard(id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guards WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/guard/notify-expiry", methods=["POST"])
def notify_expiry():
    data = request.get_json()
    email = data.get("email")
    vehicle = data.get("vehicle")
    location = data.get("location")
    slot = data.get("slot")

    if not email:
        return jsonify({"success": False, "message": "User email not found."})

    try:
        msg = MIMEText(f"""
        ⚠️ ALERT: PARKING DURATION EXPIRED ⚠️
        
        System ID: PE-SECURITY-HUD
        Priority: HIGH
        
        Notification for Vehicle: {vehicle}
        Location: {location} (Slot: {slot})
        
        SECURITY ALERT: Your reserved parking time has EXPIRED. 
        According to Nanded City Smart Parking protocols, please remove your vehicle immediately.
        
        [ AUDIO ALERT TONE: BEEEEP... BEEEEP... BEEEEP... ]
        
        Failure to remove the vehicle may result in towing or additional fines.
        
        - ParkEase Security HUD
        """)
        msg["Subject"] = f"⚠️ ACTION REQUIRED: Parking Expired - {vehicle}"
        msg["From"] = EMAIL
        msg["To"] = email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, APP_PASSWORD)
            server.sendmail(EMAIL, email, msg.as_string())

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ============================================================
# CONTACT
# ============================================================

@app.route("/send-message", methods=["POST"])
def send_message():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE)
    conn.cursor().execute(
        "INSERT INTO messages(name,email,message) VALUES(?,?,?)",
        (data.get("name"), data.get("email"), data.get("message"))
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ============================================================
# ML PREDICTION
# ============================================================

@app.route("/api/predict")
def predict():
    hour = int(request.args.get("hour", datetime.now().hour))
    result = {}

    for key, loc in ml.LOCATIONS.items():
        pct = ml.predict(key, hour)
        avail = round(loc["total"] * pct / 100)
        result[key] = {
            "name": loc["name"],
            "lat": float(loc.get("lat", 19.15)),
            "lng": float(loc.get("lng", 77.31)),
            "slots": int(avail),
            "total": int(loc["total"]),
            "pct": float(round(float(pct), 1)),
            "zone": str(loc["zone"])
        }
    return jsonify(result)

# ============================================================
# CHATBOT API
# ============================================================

@app.route("/api/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json()
    query = data.get("query", "").lower()
    
    # Check for specific locations mentioned in query
    found_loc = None
    for key, loc in ml.LOCATIONS.items():
        if key in query or loc["name"].lower() in query:
            found_loc = key
            break

    if found_loc:
        hour = datetime.now().hour
        pct = ml.predict(found_loc, hour)
        name = ml.LOCATIONS[found_loc]["name"]
        resp = f"Currently, {name} is {round(pct)}% available. Based on our ML pattern, it's a good time to park!"
    elif "hello" in query or "hi" in query:
        resp = "Hello! I'm your ParkEase Assistant. Ask me about parking availability in Nanded!"
    elif "available" in query or "parking" in query:
        resp = "You can check real-time availability on the dashboard. Most central areas are 60-80% free right now."
    elif "book" in query:
        resp = "To book a slot, click on any marker on the map and then click 'View Available Slots'."
    elif "cost" in query or "price" in query:
        resp = "The standard parking rate is ₹30 per hour across all Nanded City zones."
    else:
        resp = "I'm specializing in Nanded parking. Try 'Shivaji Chowk availability' or 'How much is it?'"
        
    return jsonify({"reply": resp})

# ============================================================
# CSV UPLOAD & RETRAIN
# ============================================================

@app.route("/upload-csv", methods=["POST"])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"})

    if file and file.filename.endswith('.csv'):
        path = f"uploads/{file.filename}"
        file.save(path)
        try:
            ml.train_from_csv(path)
            return jsonify({
                "success": True, 
                "message": "Model retrained successfully!",
                "accuracy": ml.accuracy,
                "records": ml.records
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Training Error: {str(e)}"})

    return jsonify({"success": False, "message": "Invalid file format"})

# ============================================================
# PAYMENTS (RAZORPAY)
# ============================================================

@app.route("/api/create-order", methods=["POST"])
def create_order():
    data = request.get_json()
    amount = int(data.get("amount", 30)) * 100 # Razorpay expects amount in paise
    
    order_data = {
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    }
    
    try:
        order = client.order.create(data=order_data)
        return jsonify({"success": True, "order_id": order['id'], "key": RAZORPAY_KEY_ID})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data = request.get_json()
    try:
        # Verify the signature
        params_dict = {
            'razorpay_order_id': data.get('razorpay_order_id'),
            'razorpay_payment_id': data.get('razorpay_payment_id'),
            'razorpay_signature': data.get('razorpay_signature')
        }
        client.utility.verify_payment_signature(params_dict)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": "Payment verification failed"})

# ============================================================
# BOOK SLOT
# ============================================================

@app.route("/book-slot", methods=["POST"])
def book_slot():
    # Use form data if file is present, otherwise json
    if request.is_json:
        data = request.get_json()
        file = None
    else:
        data = request.form
        file = request.files.get('screenshot')

    loc_key = data.get("loc_key")
    slot_id = data.get("slot_id")
    name = data.get("name")
    email = data.get("email")
    mobile = data.get("mobile")
    aadhar = data.get("aadhar")
    vehicle = data.get("vehicle")
    hours = int(data.get("hours", 1))
    charge = int(data.get("charge", 30))
    
    screenshot_name = None
    if file:
        screenshot_name = f"pay_{random.randint(1000,9999)}_{file.filename}"
        file.save(f"static/uploads/{screenshot_name}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE location=? AND slot_id=?", (loc_key, slot_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Slot already booked!"})

    time = datetime.now().strftime("%d/%m %H:%M")
    cursor.execute("""
        INSERT INTO bookings(location, slot_id, name, email, mobile, aadhar, vehicle, time, hours, charge, payment_status, screenshot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (loc_key, slot_id, name, email, mobile, aadhar, vehicle, time, hours, charge, 'Pending', screenshot_name))

    conn.commit()
    conn.close()

    if loc_key not in slot_bookings:
        slot_bookings[loc_key] = {}
    slot_bookings[loc_key][slot_id] = {"user": name, "time": time}

    booking_id = f"PK{abs(hash(loc_key + slot_id)) % 9999:04d}"

    # Notify all clients about the new booking (Real-time update)
    socketio.emit('slot_updated', {
        "loc_key": loc_key,
        "slot_id": slot_id,
        "status": "booked",
        "user": name
    })

    return jsonify({"success": True, "booking_id": booking_id})

# ============================================================
# GET BOOKINGS
# ============================================================

@app.route("/get-bookings")
def get_bookings():
    loc_key = request.args.get("key", "")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT slot_id,name,time FROM bookings WHERE location=?", (loc_key,))
    rows = cursor.fetchall()
    conn.close()

    data = {}
    for slot, name, time in rows:
        data[slot] = {"user": name, "time": time}

    return jsonify({"success": True, "data": data})

# ============================================================
# CANCEL BOOKING
# ============================================================

@app.route("/cancel-booking", methods=["POST"])
def cancel_booking():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE location=? AND slot_id=?",
                   (data.get("loc_key"), data.get("slot_id")))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ============================================================
# GUARD DASHBOARD
# ============================================================

@app.route("/guard-dashboard")
def guard_dashboard():
    area_key = request.args.get("area")
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if area_key:
        cursor.execute("SELECT * FROM bookings WHERE location=?", (area_key,))
    else:
        cursor.execute("SELECT * FROM bookings")
    bookings = [dict(row) for row in cursor.fetchall()]
    conn.close()

    area_name = "All Areas"
    if area_key and area_key in ml.LOCATIONS:
        area_name = ml.LOCATIONS[area_key]["name"]

    now = datetime.now()
    processed_bookings = []
    
    for b in bookings:
        try:
            # Parse time (format: %d/%m %H:%M)
            # Since year is not in the format, we assume current year
            booking_time = datetime.strptime(f"{now.year}/{b['time']}", "%Y/%d/%m %H:%M")
            expiry_time = booking_time + timedelta(hours=b['hours'])
            
            diff = expiry_time - now
            expired = diff.total_seconds() <= 0
            
            if expired:
                status = "EXPIRED"
                time_left = "Time Up!"
            else:
                status = "ACTIVE"
                mins = int(diff.total_seconds() / 60)
                time_left = f"{mins // 60}h {mins % 60}m"
                
            b['status'] = status
            b['time_left'] = time_left
            processed_bookings.append(b)
        except Exception as e:
            print(f"Time parsing error: {e}")
            b['status'] = "UNKNOWN"
            b['time_left'] = "--"
            processed_bookings.append(b)

    return render_template("guard_dashboard.html", bookings=processed_bookings, area_name=area_name)

# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    init_db()
    print("🚀 ParkEase Server Online")
    print("Local Access: http://127.0.0.1:5000")
    print("Network Access: Check your computer's IP address (e.g. http://192.168.1.5:5000)")
    app.run(debug=True, host='0.0.0.0', port=5000)