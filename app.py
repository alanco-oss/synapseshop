import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

APP_NAME = os.getenv("APP_NAME", "synapseshop-api")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
DB_HOST = os.getenv("DB_HOST", "not-set")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = json.dumps(
                {"status": "ok", "app": APP_NAME, "db_host": DB_HOST}
            ).encode("utf-8")
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')

    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)


def main():
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), HealthHandler)
    logging.info(
        "%s iniciado em http://%s:%d/health", APP_NAME, APP_HOST, APP_PORT
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
