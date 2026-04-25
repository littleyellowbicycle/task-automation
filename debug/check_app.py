from dotenv import load_dotenv
load_dotenv()
import os
app_id = os.getenv("FEISHU_APP_ID", "")
print("App ID:", app_id)
print("Prefix:", app_id[:6] if len(app_id) >= 6 else app_id)
