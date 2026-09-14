import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sys

# SQLite database for storing analytics events locally
db = sqlite3.connect(":memory:", check_same_thread=False)
cur = db.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    event_name TEXT,
    timestamp TEXT,
    org_id INTEGER,
    user_id INTEGER,
    session_id TEXT,
    properties TEXT,
    source TEXT,
    ip TEXT
)
""")
db.commit()


class TinybirdMockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep logs clean
        sys.stderr.write(f"[tinybird-mock] {self.address_string()} - {format % args}\n")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if parsed.path.startswith("/v0/events"):
            try:
                # Handle NDJSON or standard JSON payload
                text = body.decode("utf-8").strip()
                events = []
                if text.startswith("{"):
                    # Could be single object or NDJSON
                    for line in text.splitlines():
                        if line.strip():
                            events.append(json.loads(line))
                elif text.startswith("["):
                    events = json.loads(text)

                for ev in events:
                    cur.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            ev.get("event_name", ""),
                            ev.get("timestamp", ""),
                            ev.get("org_id", 0),
                            ev.get("user_id", 0),
                            ev.get("session_id", ""),
                            json.dumps(ev.get("properties", {})),
                            ev.get("source", ""),
                            ev.get("ip", ""),
                        )
                    )
                db.commit()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"successful_rows": 1, "quarantined_rows": 0}')
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

        elif parsed.path.startswith("/v0/sql"):
            # Tinybird Query API returns ClickHouse-compatible JSON structure
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "data": [],
                "rows": 0,
                "meta": [],
                "statistics": {"elapsed": 0.001, "rows_read": 0, "bytes_read": 0},
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found"}')

    def do_GET(self):
        if self.path in ("/health", "/v0/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "mock": "tinybird"}')
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("0.0.0.0", port), TinybirdMockHandler)
    print(f"Tinybird Mock Analytics Server listening on port {port}...")
    server.serve_forever()
