"""À lancer UNE FOIS sur ton ordinateur pour obtenir le GOOGLE_REFRESH_TOKEN (compte propriétaire du Drive).
   pip install google-auth-oauthlib
   python scripts/drive_auth.py chemin/vers/client_secret.json
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], ["https://www.googleapis.com/auth/drive"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nGOOGLE_CLIENT_ID     =", creds.client_id)
print("GOOGLE_CLIENT_SECRET =", creds.client_secret)
print("GOOGLE_REFRESH_TOKEN =", creds.refresh_token)
