
import smtplib
import imaplib
import email
import pandas as pd
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI
from datetime import datetime
from config1.config import CONFIG
from utils.email_templates import get_email_template
from utils.logger import logger
from services.mongodb_service import get_collection

def send_email(to_email, subject, body, scam_report_id):
    try:
        logger.debug(f"Preparing to send email to {to_email} with subject: {subject}")
        msg = MIMEMultipart()
        msg["From"] = CONFIG["email"]["user"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(CONFIG["email"]["host"], CONFIG["email"]["port"]) as server:
            server.starttls()
            server.login(CONFIG["email"]["user"], CONFIG["email"]["pass"])
            server.send_message(msg)
        
        # Store email sent status in sent_emails collection
        get_collection("sent_emails", db_type="email_transactions").insert_one({
            "scam_report_id": scam_report_id,
            "category": get_category_from_email(to_email),
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "sent_at": datetime.utcnow(),
            "status": "sent"
        })
        logger.info(f"Email sent to {to_email} for scam report {scam_report_id}")
    except Exception as e:
        # Store failed email attempt in sent_emails collection
        get_collection("sent_emails", db_type="email_transactions").insert_one({
            "scam_report_id": scam_report_id,
            "category": get_category_from_email(to_email),
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "sent_at": datetime.utcnow(),
            "status": "failed",
            "error": str(e)
        })
        logger.error(f"Error sending email to {to_email} for scam report {scam_report_id}: {e}")

def check_nodal_responses():
    try:
        logger.debug("Connecting to IMAP server to check for nodal responses")
        mail = imaplib.IMAP4_SSL(CONFIG["email"]["imap_server"])
        mail.login(CONFIG["email"]["user"], CONFIG["email"]["pass"])
        mail.select("inbox")

        result, data = mail.search(None, "ALL")
        email_ids = data[0].split()
        logger.debug(f"Found {len(email_ids[-30:])} recent emails to check")

        nodal_emails = set(CONFIG["nodal_officers"].values())

        for email_id in reversed(email_ids[-30:]):
            result, message_data = mail.fetch(email_id, "(RFC822)")
            raw_email = message_data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_email = email.utils.parseaddr(msg.get("From"))[1].lower()
            if from_email not in nodal_emails:
                logger.debug(f"Skipping email from {from_email} (not a nodal officer)")
                continue

            logger.debug(f"Processing email from {from_email} with subject: {msg['Subject']}")
            for part in msg.walk():
                if "attachment" in str(part.get("Content-Disposition", "")) and part.get_filename().endswith(".xlsx"):
                    logger.debug(f"Found Excel attachment: {part.get_filename()}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                        tmp.write(part.get_payload(decode=True))
                        tmp_path = tmp.name
                    process_attachment(tmp_path, from_email, msg["Subject"])
                    os.remove(tmp_path)

        mail.logout()
    except Exception as e:
        logger.error(f"Error checking nodal responses: {e}")

def process_attachment(filepath, source_email, email_subject):
    try:
        logger.debug(f"Processing Excel attachment from {source_email}")
        df = pd.read_excel(filepath)
        if df.empty:
            logger.info("Empty Excel attachment received")
            return

        client = OpenAI(
            base_url=CONFIG["openrouter"]["base_url"],
            api_key=CONFIG["openrouter"]["api_key"]
        )

        for _, row in df.iterrows():
            suspect_value = infer_suspect_value(row)
            content = f"Structure this data properly as JSON: {row.to_dict()}"

            logger.debug(f"Formatting row with suspect value: {suspect_value}")
            completion = client.chat.completions.create(
                model="google/gemma-3n-e4b-it:free",
                messages=[{"role": "user", "content": content}]
            )

            formatted = completion.choices[0].message.content
            logger.info(f"Processed attachment from {source_email} for suspect {suspect_value}, JSON: {formatted}")
    except Exception as e:
        logger.error(f"Failed to process attachment from {source_email}: {e}")

def infer_suspect_value(row):
    for key in row.keys():
        if any(k in key.lower() for k in ["mobile", "account", "upi"]):
            return str(row[key])
    return "unknown"

def get_category_from_email(email):
    for category, email_address in CONFIG["nodal_officers"].items():
        if email_address == email:
            return category
    return "unknown"

def send_email_to_nodal_officers(data):
    logger.debug(f"Processing scam report data: {data}")
    categories = {
        "phones": ("dot", "Request for Phone Number Details"),
        "account_numbers": ("bank", "Request for Account Holder Details and Transaction History – Suspected Involvement in Online Scam Activity"),
        "socials": ("meta", "Request for Social Media Account Details and Login Metadata"),
        "upi_ids": ("payments", "Request for Merchant and Transaction Details – Suspected Online Scam Activity")
    }

    for field, (officer, subject) in categories.items():
        suspects = data.get(field, [])
        logger.debug(f"Checking field {field} for officer {officer}: {suspects}")
        if suspects:
            email_body = get_email_template(officer, data)
            logger.debug(f"Generated email body for {officer}: {email_body[:100]}...")
            send_email(
                to_email=CONFIG["nodal_officers"][officer],
                subject=subject,
                body=email_body,
                scam_report_id=str(data["_id"])
            )
        else:
            logger.debug(f"No suspects found in field {field}, skipping email for {officer}")
