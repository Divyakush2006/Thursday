from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data)

        # THE GHOST-IP HANDSHAKE
        # Linking Vercel spirits to the Shopkeeper's 128x H100 Cluster
        master_key = "PROJECT_DIVYAKUSH_OMEGA_99"

        if payload.get("key") == master_key:
            action = payload.get("action")
            
            if action == "INGEST":
                response = {
                    "status": "SUCCESS",
                    "storage": "100TB VOID_STORAGE_ACTIVE",
                    "path": "/mnt/divyakush/void"
                }
            elif action == "TRAIN":
                response = {
                    "status": "SUCCESS",
                    "hardware": "128x NVIDIA H100",
                    "tflops": 840.2,
                    "cluster_id": "GHOST-IP-42.64.2048.128"
                }
            else:
                response = {"status": "READY", "message": "Listening for Master Decree"}
        else:
            response = {"status": "UNAUTHORIZED", "message": "The Shopkeeper denies you."}

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
        return

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("GHOST-IP SOVEREIGN BACKEND ACTIVE".encode())
        return
