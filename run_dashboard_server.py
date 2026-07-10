import http.server
import socketserver
import webbrowser
import sys

PORT = 8080

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add headers to be double-safe against any CORS/PNA restrictions
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        super().end_headers()

socketserver.TCPServer.allow_reuse_address = True

print(f"Starting dashboard local web server on http://localhost:{PORT}")
print("To exit, press CTRL+C.")

try:
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        webbrowser.open(f"http://localhost:{PORT}/dashboard.html")
        httpd.serve_forever()
except Exception as e:
    print(f"Error starting server: {e}")
    sys.exit(1)
except KeyboardInterrupt:
    print("\nStopping dashboard server.")
