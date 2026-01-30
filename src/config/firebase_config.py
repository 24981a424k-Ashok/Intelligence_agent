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
            service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            if service_account_path and os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized with service account.")
            else:
                # Fallback to default credentials (for production/cloud)
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
