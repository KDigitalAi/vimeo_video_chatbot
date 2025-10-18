#!/usr/bin/env python3
"""
Simple HTTP server to serve the frontend chatbot UI.
This ensures that index.html is served as the default page and disables directory listing.
"""
import http.server
import socketserver
import os
import sys
import urllib.parse

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        # Always serve index.html for root requests
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
        
        # Disable directory listing by redirecting to index.html
        if self.path.endswith('/'):
            self.path = '/index.html'
        
        return super().do_GET()
    
    def list_directory(self, path):
        """Override to disable directory listing - always serve index.html instead."""
        self.path = '/index.html'
        return super().do_GET()

def main():
    PORT = 3000
    
    # Change to the frontend directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(script_dir, 'frontend')
    
    if not os.path.exists(frontend_dir):
        print(f"Error: Frontend directory not found at {frontend_dir}")
        print("Please ensure the frontend folder exists in the project root.")
        sys.exit(1)
    
    os.chdir(frontend_dir)
    
    print(f"Starting frontend server on port {PORT}")
    print(f"Serving from: {os.getcwd()}")
    print(f"Access the chatbot at: http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")
    
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
            sys.exit(0)

if __name__ == "__main__":
    main()
