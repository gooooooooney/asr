#!/usr/bin/env python3
"""
Simple HTTP server for AI Voice Note App
Serves the application with proper MIME types and CORS headers
"""

import http.server
import socketserver
import os
import sys
from http import HTTPStatus
import mimetypes

# Configuration
PORT = 8007
HOST = '0.0.0.0'

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with CORS headers."""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def end_headers(self):
        """Add CORS headers to all responses."""
        self.send_cors_headers()
        super().end_headers()
    
    def send_cors_headers(self):
        """Send CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(HTTPStatus.OK)
        self.send_cors_headers()
        self.end_headers()
    
    def guess_type(self, path):
        """Guess the MIME type of a file with custom handling for ES modules."""
        mimetype = super().guess_type(path)
        
        # Ensure JavaScript files have the correct MIME type
        if path.endswith('.js'):
            return 'application/javascript'
        elif path.endswith('.mjs'):
            return 'application/javascript'
        elif path.endswith('.wasm'):
            return 'application/wasm'
        
        return mimetype
    
    def log_message(self, format, *args):
        """Custom log format."""
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")

def main():
    """Start the HTTP server."""
    # Ensure proper MIME types
    mimetypes.init()
    mimetypes.add_type('application/javascript', '.js')
    mimetypes.add_type('application/javascript', '.mjs')
    mimetypes.add_type('application/wasm', '.wasm')
    
    try:
        with socketserver.TCPServer((HOST, PORT), CORSRequestHandler) as httpd:
            print(f"\n🚀 AI Voice Note Server is running!")
            print(f"📍 Local:    http://localhost:{PORT}")
            print(f"📍 Network:  http://{HOST}:{PORT}")
            print(f"\n📄 Main page: http://localhost:{PORT}/index-final.html")
            print(f"📄 Test VAD: http://localhost:{PORT}/test-vad.html")
            print(f"📄 Test Intent: http://localhost:{PORT}/test-intent-v2.html")
            print(f"\n⚡ Features:")
            print(f"   - CORS enabled for all origins")
            print(f"   - Proper MIME types for ES modules")
            print(f"   - WebAssembly support")
            print(f"\n🛑 Press Ctrl+C to stop the server\n")
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")
        sys.exit(0)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"\n❌ Error: Port {PORT} is already in use.")
            print(f"   Try using a different port or stop the other process.")
            print(f"\n   To find the process using port {PORT}:")
            print(f"   Linux/Mac: lsof -i :{PORT}")
            print(f"   Windows: netstat -ano | findstr :{PORT}\n")
        else:
            print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()