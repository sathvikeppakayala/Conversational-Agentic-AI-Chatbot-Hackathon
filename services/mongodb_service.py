
from pymongo import MongoClient
from config1.config import CONFIG
from utils.logger import logger

client = None
db = None
email_transactions_client = None
email_transactions_db = None

def connect_db():
    global client, db
    try:
        client = MongoClient(
            CONFIG["mongo_uri"],
            maxPoolSize=50,  # Connection pooling
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        db = client.get_database("Phantom-Protocol")
        client.admin.command('ping')  # Test connection
        logger.info("Connected to Phantom-Protocol MongoDB")
        return db
    except Exception as e:
        logger.error(f"Phantom-Protocol MongoDB connection error: {e}")
        raise

def connect_email_transactions_db():
    global email_transactions_client, email_transactions_db
    try:
        email_transactions_client = MongoClient(
            CONFIG["email_transactions_mongo_uri"],
            maxPoolSize=50,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        email_transactions_db = email_transactions_client.get_database("email_transactions")
        email_transactions_client.admin.command('ping')  # Test connection
        logger.info("Connected to email_transactions MongoDB")
        return email_transactions_db
    except Exception as e:
        logger.error(f"email_transactions MongoDB connection error: {e}")
        raise

def get_collection(collection_name, db_type="scam_database"):
    if not collection_name:
        logger.error("Collection name cannot be empty")
        raise ValueError("Collection name cannot be empty")
    if db_type not in ["scam_database", "email_transactions"]:
        logger.error(f"Invalid db_type: {db_type}")
        raise ValueError(f"Invalid db_type: {db_type}")
    
    if db_type == "scam_database":
        global db
        if db is None:
            connect_db()
        if collection_name not in db.list_collection_names():
            logger.warning(f"Collection {collection_name} not found in Phantom-Protocol")
        return db[collection_name]
    elif db_type == "email_transactions":
        global email_transactions_db
        if email_transactions_db is None:
            connect_email_transactions_db()
        if collection_name not in email_transactions_db.list_collection_names():
            logger.warning(f"Collection {collection_name} not found in email_transactions")
        return email_transactions_db[collection_name]

def list_collections(db_type="scam_database"):
    """List available collections in the specified database."""
    try:
        if db_type == "scam_database":
            global db
            if db is None:
                connect_db()
            collections = db.list_collection_names()
            logger.info(f"Collections in Phantom-Protocol: {collections}")
            return collections
        elif db_type == "email_transactions":
            global email_transactions_db
            if email_transactions_db is None:
                connect_email_transactions_db()
            collections = email_transactions_db.list_collection_names()
            logger.info(f"Collections in email_transactions: {collections}")
            return collections
        else:
            logger.error(f"Invalid db_type for listing collections: {db_type}")
            raise ValueError(f"Invalid db_type: {db_type}")
    except Exception as e:
        logger.error(f"Error listing collections for {db_type}: {e}")
        raise

def close_connections():
    """Close MongoDB connections."""
    global client, email_transactions_client
    try:
        if client:
            client.close()
            logger.info("Closed Phantom-Protocol MongoDB connection")
        if email_transactions_client:
            email_transactions_client.close()
            logger.info("Closed email_transactions MongoDB connection")
    except Exception as e:
        logger.error(f"Error closing MongoDB connections: {e}")
