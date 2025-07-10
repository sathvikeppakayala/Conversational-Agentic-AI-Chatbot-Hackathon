
import os
from dotenv import load_dotenv

load_dotenv()
CONFIG = {
    "mongo_uri": os.getenv("MONGO_URI", "MONGO_URI"),
    "email_transactions_mongo_uri": os.getenv("EMAIL_TRANSACTIONS_MONGO_URI", "MONGO_URI"),
    "email": {
        "host": os.getenv("EMAIL_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("EMAIL_PORT", 587)),
        "user": os.getenv("EMAIL_USER", "isronasaesa@gmail.com"),
        "pass": os.getenv("EMAIL_PASS", "abcd#### aaka"),
        "imap_server": os.getenv("IMAP_SERVER", "imap.gmail.com")
    },
    "nodal_officers": {
        "dot": os.getenv("DOT_EMAIL", "dot.nodal@domain.com"),
        "bank": os.getenv("BANK_EMAIL", "bank.nodal@domain.com"),
        "meta": os.getenv("META_EMAIL", "meta.nodal@domain.com"),
        "payments": os.getenv("PAYMENTS_EMAIL", "payments.nodal@domain.com")
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY", "MNOP")
    }
}
