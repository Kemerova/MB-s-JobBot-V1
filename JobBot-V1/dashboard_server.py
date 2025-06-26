#!/usr/bin/env python3
"""
Job Hunter Dashboard Viewer
===========================

Lightweight web server to serve the job dashboard and automatically open it in the browser.
"""

import os
import sys
import json
import webbrowser
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import socketserver


class JobDashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler for serving job dashboard files"""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        super().__init__(*args, directory="output", **kwargs)
    
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging to keep output clean
        pass


class DashboardServer:
    """Lightweight dashboard server"""
    
    def __init__(self, port=8080, output_dir="output"):
        self.port = port
        self.output_dir = output_dir
        self.server = None
        self.server_thread = None
        
    def find_available_port(self, start_port=8080, max_tries=10):
        """Find an available port starting from start_port"""
        import socket
        
        for port in range(start_port, start_port + max_tries):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                return port
            except OSError:
                continue
        
        # Fallback to random port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            return s.getsockname()[1]
    
    def start_server(self):
        """Start the dashboard server"""
        # Change to output directory
        if os.path.exists(self.output_dir):
            os.chdir(self.output_dir)
        else:
            print(f"⚠️  Output directory {self.output_dir} not found")
            return False
        
        # Find available port
        self.port = self.find_available_port(self.port)
        
        try:
            # Create server
            self.server = HTTPServer(('localhost', self.port), JobDashboardHandler)
            
            print(f"🌐 Dashboard server starting on http://localhost:{self.port}")
            print(f"📁 Serving files from: {os.getcwd()}")
            
            # Start server in background thread
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start dashboard server: {e}")
            return False
    
    def stop_server(self):
        """Stop the dashboard server"""
        if self.server:
            print("🛑 Stopping dashboard server...")
            self.server.shutdown()
            self.server.server_close()
            self.server = None
    
    def open_dashboard(self, filename="job_dashboard.html", delay=2):
        """Open the dashboard in the default web browser"""
        if not self.server:
            print("❌ Server not running")
            return False
        
        # Wait a moment for server to fully start
        time.sleep(delay)
        
        dashboard_url = f"http://localhost:{self.port}/{filename}"
        
        try:
            print(f"🔗 Opening dashboard: {dashboard_url}")
            webbrowser.open(dashboard_url)
            return True
        except Exception as e:
            print(f"❌ Failed to open browser: {e}")
            print(f"💡 Manually open: {dashboard_url}")
            return False
    
    def serve_and_open(self, dashboard_file="job_dashboard.html", auto_open=True):
        """Start server and optionally open dashboard"""
        if not self.start_server():
            return False
        
        if auto_open:
            self.open_dashboard(dashboard_file)
        
        return True
    
    def get_dashboard_url(self, filename="job_dashboard.html"):
        """Get the full URL to the dashboard"""
        if self.server:
            return f"http://localhost:{self.port}/{filename}"
        return None


def check_dashboard_files(output_dir="output"):
    """Check if required dashboard files exist"""
    files_to_check = [
        "job_dashboard.html",
        "jobs_data.json"
    ]
    
    missing_files = []
    for filename in files_to_check:
        filepath = os.path.join(output_dir, filename)
        if not os.path.exists(filepath):
            missing_files.append(filename)
    
    return missing_files


def serve_dashboard(output_dir="output", port=8080, auto_open=True, dashboard_file="job_dashboard.html"):
    """
    Main function to serve the job dashboard
    
    Args:
        output_dir: Directory containing dashboard files
        port: Port to serve on (will find available port if busy)
        auto_open: Whether to automatically open browser
        dashboard_file: HTML file to open
    
    Returns:
        DashboardServer instance
    """
    print("🚀 Starting JobBot Dashboard Server...")
    
    # Check if dashboard files exist
    missing_files = check_dashboard_files(output_dir)
    if missing_files:
        print(f"⚠️  Missing dashboard files: {', '.join(missing_files)}")
        print("💡 Run the job hunter first to generate dashboard files")
        return None
    
    # Create and start server
    server = DashboardServer(port, output_dir)
    
    if server.serve_and_open(dashboard_file, auto_open):
        print("✅ Dashboard server running successfully!")
        print(f"🌐 Dashboard URL: {server.get_dashboard_url(dashboard_file)}")
        print("🛑 Press Ctrl+C to stop the server")
        return server
    else:
        print("❌ Failed to start dashboard server")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="JobBot Dashboard Server")
    parser.add_argument('--port', type=int, default=8080, help='Port to serve on')
    parser.add_argument('--output-dir', default='output', help='Output directory')
    parser.add_argument('--no-open', action='store_true', help='Don\'t auto-open browser')
    parser.add_argument('--file', default='job_dashboard.html', help='Dashboard file to open')
    
    args = parser.parse_args()
    
    try:
        server = serve_dashboard(
            output_dir=args.output_dir,
            port=args.port,
            auto_open=not args.no_open,
            dashboard_file=args.file
        )
        
        if server:
            try:
                # Keep server running
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Shutting down dashboard server...")
                server.stop_server()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)