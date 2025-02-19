import os
import json
import firebase_admin
from firebase_admin import credentials

firebase_config = os.getenv("FIREBASE_CONFIG")
if firebase_config:
    # Parse the JSON string from the env variable
    service_account_info = json.loads(firebase_config)
    cred = credentials.Certificate(service_account_info)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)
else:
    raise Exception("FIREBASE_CONFIG environment variable not found")