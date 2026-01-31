import os
import firebase_admin
from firebase_admin import credentials, messaging, auth
from loguru import logger

def initialize_firebase():
    """
    Initialize Firebase Admin SDK using service account or default credentials.
    Expects FIREBASE_SERVICE_ACCOUNT_PATH environment variable for local testing.
    """
    try:
        if not firebase_admin._apps:
            # 1. Try JSON string from ENV (for Cloud/Render)
            service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if service_account_json:
                import json
                try:
                    cred_dict = json.loads(service_account_json)
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized using JSON string from environment.")
                    return
                except Exception as ex:
                    logger.error(f"Failed to load Firebase credentials from JSON string: {ex}")

            # 2. Try file path
            service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            if service_account_path and os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized with service account file.")
            else:
                # 3. Fallback to default
                firebase_admin.initialize_app()
                logger.info("Firebase Admin SDK initialized with default credentials.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")

def verify_token(id_token: str):
    """Verify Firebase ID Token from frontend."""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None
