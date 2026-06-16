import http.server
import urllib.parse
import webbrowser
import requests
import ssl
import os
import threading
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_APP_ID = "1524949909008915"
INSTAGRAM_APP_SECRET = "035cc8b1a80215fc6dd902954bc04ea5"
REDIRECT_URI = "https://localhost:8080/"

AUTH_URL = (
    f"https://www.instagram.com/oauth/authorize"
    f"?force_reauth=true"
    f"&client_id={INSTAGRAM_APP_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope=instagram_business_basic,instagram_business_content_publish"
)

received_code = None


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global received_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            received_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>OK! Claude Code will exchange the code now.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code received.")

    def log_message(self, format, *args):
        pass  # suppress server logs


def run_server():
    # Create a self-signed SSL context
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.check_hostname = False
    # Generate a temp self-signed cert
    import subprocess
    if not os.path.exists("cert.pem"):
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", "key.pem", "-out", "cert.pem",
            "-days", "1", "-nodes",
            "-subj", "/CN=localhost"
        ], check=True, capture_output=True)
    ctx.load_cert_chain("cert.pem", "key.pem")

    server = http.server.HTTPServer(("localhost", 8080), Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.handle_request()


print("Opening browser for Instagram login...")
print(f"\nAuth URL:\n{AUTH_URL}\n")

t = threading.Thread(target=run_server)
t.daemon = True
t.start()

webbrowser.open(AUTH_URL)

print("Waiting for redirect... (login in the browser)")
t.join(timeout=120)

if not received_code:
    print("ERROR: No code received within 2 minutes.")
    exit(1)

print(f"\nCode received! Exchanging for token...")

# Exchange code for short-lived token
r = requests.post(
    "https://api.instagram.com/oauth/access_token",
    data={
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": received_code,
    }
)
data = r.json()
print("Short-lived token response:", data)

if "access_token" not in data:
    print("ERROR: Failed to get token")
    exit(1)

short_token = data["access_token"]
ig_user_id = data.get("user_id")
print(f"Instagram User ID: {ig_user_id}")

# Exchange for long-lived token (60 days)
r2 = requests.get(
    "https://graph.instagram.com/access_token",
    params={
        "grant_type": "ig_exchange_token",
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "access_token": short_token,
    }
)
data2 = r2.json()
print("Long-lived token response:", data2)

if "access_token" in data2:
    long_token = data2["access_token"]
    print(f"\n=== SUCCESS ===")
    print(f"Instagram User ID : {ig_user_id}")
    print(f"Long-lived Token  : {long_token}")

    # Update .env
    env_path = ".env"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"INSTAGRAM_ACCOUNT_ID={ig_user_id}\n")
        f.write(f"ACCESS_TOKEN={long_token}\n")
    print("\n.env updated successfully!")
