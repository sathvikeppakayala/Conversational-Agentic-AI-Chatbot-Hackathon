
from flask import Flask, request, redirect, url_for, render_template, jsonify, session, make_response
from services.mongodb_service import get_collection
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

app = Flask(__name__, template_folder='.')
app.secret_key = 'your-secret-key-123'  # Replace with a secure key in production

def calculate_risk_score(collection, identifier, field):
    """Count occurrences of an identifier in a field across the collection."""
    return collection.count_documents({field: identifier})

def parse_datetime(dt):
    """Convert string datetime to datetime object, or return as-is if already datetime."""
    if isinstance(dt, str):
        try:
            # Try ISO format (e.g., "2025-07-06T12:25:30Z")
            return datetime.strptime(dt.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                # Try standard format (e.g., "2025-07-06 12:25:30")
                return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Try DD-MM-YYYY format (e.g., "06-07-2025 12:25:30")
                return datetime.strptime(dt, "%d-%m-%Y %H:%M:%S")
    return dt

@app.route('/')
@app.route('/login')
def serve_index():
    return render_template('index.html')

@app.route('/auth/google')
def auth_google():
    return "Google Login: Coming soon (requires JavaScript for OAuth)"

@app.route('/auth/github')
def auth_github():
    return "GitHub Login: Coming soon (requires JavaScript for OAuth)"

@app.route('/auth/gmail')
def auth_gmail():
    return "Gmail Login: Coming soon (requires JavaScript for OAuth)"

@app.route('/login/admin', methods=['POST'])
def login_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == 'admin' and password == 'aDmin@123':
        session['logged_in'] = True
        return redirect('/dashboard')
    else:
        return redirect('/login')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if not session.get('logged_in'):
        return redirect('/login')
    collection = get_collection("contacts", db_type="scam_database")
    email_collection = get_collection("sent_emails", db_type="email_transactions")
    search_query = request.args.get('search', '').strip()
    
    query = {"classification": {"$in": ["scammer", "scammer_image", "scammer_voice"]}}
    if search_query:
        query["$or"] = [
            {"user": search_query},
            {"upi_ids": search_query},
            {"phones": search_query},
            {"account_numbers": search_query},
            {"socials": search_query}
        ]
    
    scammers = []
    for doc in collection.find(query).sort("datetime", -1).limit(10000):
        risk_score = 0
        for field in ["upi_ids", "phones", "account_numbers", "socials"]:
            for item in doc.get(field, []):
                risk_score += calculate_risk_score(collection, item, field)
        
        dt = parse_datetime(doc.get("datetime", datetime.now()))
        
        scammers.append({
            "user": doc.get("user", "Unknown"),
            "text": doc.get("text", ""),
            "upi_ids": doc.get("upi_ids", []),
            "phones": doc.get("phones", []),
            "account_numbers": doc.get("account_numbers", []),
            "socials": doc.get("socials", []),
            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "risk_score": risk_score
        })
    
    emails = []
    for doc in email_collection.find().sort("sent_at", -1).limit(10000):
        dt = parse_datetime(doc.get("sent_at", datetime.now()))
        emails.append({
            "_id": str(doc.get("_id")),
            "scam_report_id": doc.get("scam_report_id", "Unknown"),
            "category": doc.get("category", "Unknown"),
            "to_email": doc.get("to_email", "Unknown"),
            "subject": doc.get("subject", ""),
            "status": doc.get("status", "Unknown"),
            "sent_at": dt.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return render_template('dashboard.html', scammers=scammers, emails=emails, search_query=search_query)

@app.route('/all_scammers', methods=['GET'])
def all_scammers():
    if not session.get('logged_in'):
        return redirect('/login')
    collection = get_collection("contacts", db_type="scam_database")
    search_query = request.args.get('search', '').strip()
    
    query = {"classification": "scammer"}
    if search_query:
        query["$or"] = [
            {"user": search_query},
            {"upi_ids": search_query},
            {"phones": search_query},
            {"account_numbers": search_query},
            {"socials": search_query}
        ]
    
    scammers = []
    for doc in collection.find(query).sort("datetime", -1):
        risk_score = 0
        for field in ["upi_ids", "phones", "account_numbers", "socials"]:
            for item in doc.get(field, []):
                risk_score += calculate_risk_score(collection, item, field)
        
        dt = parse_datetime(doc.get("datetime", datetime.now()))
        
        scammers.append({
            "user": doc.get("user", "Unknown"),
            "text": doc.get("text", ""),
            "upi_ids": doc.get("upi_ids", []),
            "phones": doc.get("phones", []),
            "account_numbers": doc.get("account_numbers", []),
            "socials": doc.get("socials", []),
            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "risk_score": risk_score
        })
    
    return render_template('all_scammers.html', scammers=scammers, search_query=search_query)

@app.route('/all_emails', methods=['GET'])
def all_emails():
    if not session.get('logged_in'):
        return redirect('/login')
    email_collection = get_collection("sent_emails", db_type="email_transactions")
    search_query = request.args.get('search', '').strip()
    
    query = {}
    if search_query:
        query["$or"] = [
            {"scam_report_id": search_query},
            {"to_email": search_query},
            {"subject": search_query},
            {"category": search_query}
        ]
    
    emails = []
    for doc in email_collection.find(query).sort("sent_at", -1):
        dt = parse_datetime(doc.get("sent_at", datetime.now()))
        emails.append({
            "_id": str(doc.get("_id")),
            "scam_report_id": doc.get("scam_report_id", "Unknown"),
            "category": doc.get("category", "Unknown"),
            "to_email": doc.get("to_email", "Unknown"),
            "subject": doc.get("subject", ""),
            "status": doc.get("status", "Unknown"),
            "sent_at": dt.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return render_template('all_emails.html', emails=emails, search_query=search_query)

@app.route('/api/scammers', methods=['GET'])
def api_scammers():
    collection = get_collection("contacts", db_type="scam_database")
    search_query = request.args.get('search', '').strip()
    
    query = {"classification": {"$in": ["scammer", "scammer_image", "scammer_voice"]}}
    if search_query:
        query["$or"] = [
            {"user": search_query},
            {"upi_ids": search_query},
            {"phones": search_query},
            {"account_numbers": search_query},
            {"socials": search_query}
        ]
    
    scammers = []
    for doc in collection.find(query).sort("datetime", -1):
        risk_score = 0
        for field in ["upi_ids", "phones", "account_numbers", "socials"]:
            for item in doc.get(field, []):
                risk_score += calculate_risk_score(collection, item, field)
        
        dt = parse_datetime(doc.get("datetime", datetime.now()))
        
        scammers.append({
            "user": doc.get("user", "Unknown"),
            "text": doc.get("text", ""),
            "upi_ids": doc.get("upi_ids", []),
            "phones": doc.get("phones", []),
            "account_numbers": doc.get("account_numbers", []),
            "socials": doc.get("socials", []),
            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "risk_score": risk_score
        })
    
    return jsonify(scammers)

@app.route('/api/emails', methods=['GET'])
def api_emails():
    email_collection = get_collection("sent_emails", db_type="email_transactions")
    search_query = request.args.get('search', '').strip()
    
    query = {}
    if search_query:
        query["$or"] = [
            {"scam_report_id": search_query},
            {"to_email": search_query},
            {"subject": search_query},
            {"category": search_query}
        ]
    
    emails = []
    for doc in email_collection.find(query).sort("sent_at", -1):
        dt = parse_datetime(doc.get("sent_at", datetime.now()))
        emails.append({
            "_id": str(doc.get("_id")),
            "scam_report_id": doc.get("scam_report_id", "Unknown"),
            "category": doc.get("category", "Unknown"),
            "to_email": doc.get("to_email", "Unknown"),
            "subject": doc.get("subject", ""),
            "status": doc.get("status", "Unknown"),
            "sent_at": dt.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return jsonify(emails)

@app.route('/generate_report', methods=['GET'])
def generate_report():
    if not session.get('logged_in'):
        return redirect('/login')
    
    report_type = request.args.get('type')
    if report_type not in ['scammers', 'emails']:
        return "Invalid report type", 400
    
    # Fetch data
    if report_type == 'scammers':
        collection = get_collection("contacts", db_type="scam_database")
        query = {"classification": "scammer"}
        data = []
        for doc in collection.find(query).sort("datetime", -1):
            risk_score = 0
            for field in ["upi_ids", "phones", "account_numbers", "socials"]:
                for item in doc.get(field, []):
                    risk_score += calculate_risk_score(collection, item, field)
            dt = parse_datetime(doc.get("datetime", datetime.now()))
            data.append({
                "user": doc.get("user", "Unknown"),
                "text": doc.get("text", "")[:30],  # Truncate to fit
                "risk_score": str(risk_score),
                "upi_ids": ", ".join(doc.get("upi_ids", []) or ["None"])[:30],
                "phones": ", ".join(doc.get("phones", []) or ["None"])[:30],
                "account_numbers": ", ".join(doc.get("account_numbers", []) or ["None"])[:30],
                "socials": ", ".join(doc.get("socials", []) or ["None"])[:30],
                "datetime": dt.strftime("%Y-%m-%d %H:%M")
            })
        title = "Found Scammers Report"
        headers = ["User", "Text", "Risk Score", "UPI IDs", "Phones", "Account Numbers", "Socials", "Date"]
        table_data = [headers] + [[d["user"], d["text"], d["risk_score"], d["upi_ids"], d["phones"], d["account_numbers"], d["socials"], d["datetime"]] for d in data]
    else:
        collection = get_collection("sent_emails", db_type="email_transactions")
        data = []
        for doc in collection.find().sort("sent_at", -1):
            dt = parse_datetime(doc.get("sent_at", datetime.now()))
            data.append({
                "_id": str(doc.get("_id"))[:15],
                "scam_report_id": doc.get("scam_report_id", "Unknown")[:15],
                "category": doc.get("category", "Unknown"),
                "to_email": doc.get("to_email", "Unknown")[:20],
                "subject": doc.get("subject", "")[:30],
                "status": doc.get("status", "Unknown"),
                "sent_at": dt.strftime("%Y-%m-%d %H:%M")
            })
        title = "Email Statistics Report"
        headers = ["Email ID", "Scam Report ID", "Category", "To Email", "Subject", "Status", "Sent At"]
        table_data = [headers] + [[d["_id"], d["scam_report_id"], d["category"], d["to_email"], d["subject"], d["status"], d["sent_at"]] for d in data]
    
    # Generate PDF with ReportLab
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title, leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=30)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1  # Center
    title_style.fontSize = 12
    normal_style = styles['Normal']
    normal_style.fontSize = 5

    # Header
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
    elements.append(Spacer(1, 6))

    # Table
    table = Table(table_data, colWidths=[A4[0] / len(headers) * 0.95 for _ in headers])  # Dynamic column width
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),  # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  # Header text
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),  # Alternating row background
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Thinner grid
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEADING', (0, 0), (-1, -1), 8),  # Reduce row height
    ]))
    elements.append(table)

    # Footer
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 6)
        canvas.setFillColor(colors.HexColor('#333333'))
        canvas.drawCentredString(A4[0]/2, 15, "© 2025 Powered by Team Strategic Boosted Algorithms, contact at +91 9949284184")
        canvas.restoreState()

    # Build PDF
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

    # Create response
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)
