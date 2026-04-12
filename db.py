import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

_db = None

def get_db_connection():
    """Returns the global Firestore client, initializing it if necessary."""
    global _db
    if _db is None:
        try:
            # Avoid re-initializing if already done
            if not firebase_admin._apps:
                import json
                env_cred = os.environ.get("FIREBASE_CREDENTIALS_JSON")
                if env_cred:
                    cred_dict = json.loads(env_cred)
                    cred = credentials.Certificate(cred_dict)
                else:
                    cred_path = os.path.join(os.path.dirname(__file__), 'firebase_credentials.json')
                    if not os.path.exists(cred_path):
                        raise RuntimeError("Missing firebase_credentials.json file and FIREBASE_CREDENTIALS_JSON env var")
                    cred = credentials.Certificate(cred_path)
                
                firebase_admin.initialize_app(cred)
            _db = firestore.client()
            print("FIREBASE: Connected to Firestore successfully.")
        except Exception as e:
            print(f"FIREBASE CONNECTION ERROR: {e}")
            return None
    return _db

def release_db_connection(conn):
    """No-op for Firebase — connections are persistent and managed automatically."""
    pass

def init_db():
    """
    For Firebase/Firestore, collections are created automatically when data is
    first written to them. This function simply verifies the connection is alive.
    """
    db = get_db_connection()
    if db:
        print("DATABASE SUCCESS: Firebase Firestore is ready. Collections will be created on first write.")
    else:
        print("DATABASE INIT ERROR: Could not connect to Firestore.")

if __name__ == '__main__':
    init_db()
