from __future__ import annotations

import json
from typing import Optional, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from .feishu_bridge import FeishuBridge
from ..utils import get_logger

logger = get_logger("feishu_server")


class FeishuCallbackHandler(BaseHTTPRequestHandler):
    """Handler for Feishu card callbacks."""
    
    feishu_bridge: Optional[FeishuBridge] = None
    
    def do_POST(self):
        """Handle POST requests for callback."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            callback_data = json.loads(post_data.decode('utf-8'))
            
            logger.info(f"Received callback: {callback_data}")
            
            # Process callback
            if self.feishu_bridge:
                response = self.feishu_bridge.handle_callback(callback_data)
            else:
                response = {"code": 500, "message": "Feishu bridge not initialized"}
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {"code": 500, "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))


class FeishuServer:
    """Feishu callback server."""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8000, feishu_bridge: Optional[FeishuBridge] = None):
        self.host = host
        self.port = port
        self.feishu_bridge = feishu_bridge
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        
        # Set the bridge for the handler
        FeishuCallbackHandler.feishu_bridge = feishu_bridge
    
    def start(self):
        """Start the server."""
        try:
            self.server = HTTPServer((self.host, self.port), FeishuCallbackHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Feishu callback server started on http://{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start Feishu server: {e}")
            return False
    
    def stop(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            if self.thread:
                self.thread.join(timeout=5)
            logger.info("Feishu callback server stopped")
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self.thread and self.thread.is_alive()


def create_feishu_server(
    host: str = '0.0.0.0', 
    port: int = 8000, 
    feishu_bridge: Optional[FeishuBridge] = None
) -> FeishuServer:
    """Create and return a Feishu server instance."""
    return FeishuServer(host, port, feishu_bridge)