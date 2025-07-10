
from pymongo import MongoClient
from services.mongodb_service import get_collection
from services.email_service import send_email_to_nodal_officers, check_nodal_responses
from utils.logger import logger
import time

def start_monitoring():
    collection = get_collection("contacts", db_type="scam_database")
    
    pipeline = [{"$match": {"operationType": "insert"}}]
    try:
        with collection.watch(pipeline) as stream:
            for change in stream:
                if change["operationType"] == "insert":
                    new_document = change["fullDocument"]
                    logger.info(f"New scam report detected: {new_document['_id']}")
                    send_email_to_nodal_officers(new_document)
                
                # Check for nodal responses periodically
                check_nodal_responses()
    except Exception as e:
        logger.error(f"Change stream error: {e}")
        time.sleep(5)
        start_monitoring()  # Reconnect on error
