# messaging/services/firebase.py
import os
import firebase_admin
from firebase_admin import credentials, db
from django.conf import settings

if not firebase_admin._apps:
    # Try using the config loaded in settings
    firebase_config = settings.FIREBASE_CONFIG
    if firebase_config:
        cred = credentials.Certificate(firebase_config)
    else:
        # Optionally fallback to a cert file if needed
        cert_path = os.getenv(
            "FIREBASE_CERT_PATH", str(settings.BASE_DIR / "firebase-cert.json")
        )
        cred = credentials.Certificate(cert_path)
    firebase_admin.initialize_app(cred, {"databaseURL": settings.FIREBASE_DATABASE_URL})


def push_message(conversation_id: int, message_data: dict) -> str:
    """
    Push message data to Firebase realtime database under the conversation branch.
    Returns the generated key.
    """
    ref = db.reference(f"conversations/{conversation_id}/messages")
    new_message_ref = ref.push(message_data)
    return new_message_ref.key
