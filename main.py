
import time
from services.mongodb_service import connect_db, get_collection
from services.monitor_service import start_monitoring
from utils.logger import logger

def main():
    try:
        # Initialize MongoDB connection
        connect_db()
        # Start monitoring for new scam reports and nodal officer responses
        start_monitoring()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Application startup error: {e}")
        # Attempt to reconnect after a delay in case of failure
        time.sleep(5)
        main()

if __name__ == "__main__":
    main()
