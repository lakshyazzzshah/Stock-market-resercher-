# File: launcher.py
import sys
import subprocess
from pyngrok import ngrok

# --- 1. YOUR NGROK SETTINGS ---
# I have inserted your token from the image below:
NGROK_AUTH_TOKEN = "37ERWmJnRTzuGrqciaPOk91Auql_5NnD97ziy6NF1LF1CDyCG"

# If you have a claimed domain (like 'my-app.ngrok-free.app'), put it inside the quotes.
# If not, leave it as None, and ngrok will give you a random URL.
CUSTOM_DOMAIN = None 
# Example: CUSTOM_DOMAIN = "vishal-stock-app.ngrok-free.app"

APP_PORT = 8501

def start_app():
    # Set the token automatically
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    
    # Start the tunnel
    if CUSTOM_DOMAIN:
        url = ngrok.connect(APP_PORT, domain=CUSTOM_DOMAIN).public_url
    else:
        url = ngrok.connect(APP_PORT).public_url

    print(f"\n=======================================================")
    print(f"🔴  YOUR APP IS LIVE HERE: {url}")
    print(f"=======================================================\n")

    # Run the Stock App
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])

if __name__ == "__main__":
    start_app()