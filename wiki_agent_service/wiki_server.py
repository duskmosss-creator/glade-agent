import http.server
import socketserver
import json
import sys
import os
import time
import uuid
import socket

# Ensure we can import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import wiki_agent

PORT = 8002

class WikiAgentHandler(http.server.SimpleHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')

    def do_OPTIONS(self):
        # Handle preflight requests
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        # Normalize path to ignore trailing slashes
        path = self.path.rstrip('/')
        
        # Support both standard OpenAI path and simple root/chat
        if path not in ['/v1/chat/completions', '/chat/completions', '/chat', '/api/chat', '']:
            self.send_error(404, f"Endpoint not found: {path}")
            return

        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # --- CANCELLATION CHECKER ---
            def check_cancellation():
                """Peeks at socket to see if client disconnected."""
                try:
                    # MSG_PEEK: Check for data without consuming. 
                    # If recv returns 0 bytes, connection is closed.
                    # If explicit error (ConnectionResetError), it's closed.
                    # If timeout/blocking issue, might raise EAGAIN/BlockingIOError (ignore those).
                    chunk = self.connection.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                    if chunk == b'':
                        print("   [Server] Client disconnected (0 bytes). Cancelling...")
                        raise wiki_agent.RequestCancelledError("Client disconnected")
                except BlockingIOError:
                    pass # No data, connection alive
                except (ConnectionResetError, BrokenPipeError):
                    print("   [Server] Connection reset by client. Cancelling...")
                    raise wiki_agent.RequestCancelledError("Connection reset")
                except Exception:
                    pass # Ignore other errors to be safe

            # --- EXTRACT QUERY ---
            query = ""
            model_requested = "wiki-agent"
            # ... (Existing extraction logic) ...
            
            # 1. OpenAI Format extraction
            history = []
            if 'messages' in data:
                messages = data['messages']
                for msg in reversed(messages):
                    if msg.get('role') == 'user':
                        content_raw = msg.get('content', '')
                        if isinstance(content_raw, list):
                            text_parts = [part.get('text', '') for part in content_raw if part.get('type') == 'text']
                            query = " ".join(text_parts)
                        else:
                            query = str(content_raw)
                        break
                history = messages
                model_requested = data.get('model', model_requested)
            
            # 2. Simple Format extraction
            elif 'query' in data:
                query = data['query']
            elif 'message' in data:
                query = data['message']
            elif 'content' in data:
                query = data['content']
                
            if not query:
                self._send_json_error(400, "No query found")
                return
            
            print(f"[Server] Request: {query[:50]}...")
            
            # --- GET AGENT RESPONSE ---
            # Pass checker to agent
            response_text = wiki_agent.get_agent_response(
                query, 
                history=history, 
                include_thoughts=False,
                check_cancellation=check_cancellation
            )
            
            # --- CONSTRUCT RESPONSE ---
            if path.endswith('completions'):
                response_id = f"chatcmpl-{uuid.uuid4()}"
                timestamp = int(time.time())
                response_data = {
                    "id": response_id,
                    "object": "chat.completion",
                    "created": timestamp,
                    "model": model_requested,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": len(query) // 4,
                        "completion_tokens": len(response_text) // 4,
                        "total_tokens": (len(query) + len(response_text)) // 4
                    }
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            else:
                # Simple format
                response_data = {'response': response_text, 'status': 'success'}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except wiki_agent.RequestCancelledError:
            print("[Server] Request cancelled by client.")
            # Do not send response, connection is likely dead
            return
        except json.JSONDecodeError:
            self._send_json_error(400, "Invalid JSON body")
        except Exception as e:
            print(f"[Server Error] {e}")
            try:
                self._send_json_error(500, f"Internal Server Error: {str(e)}")
            except: pass

    def _send_json_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({'error': {'message': message, 'type': 'invalid_request_error'}}).encode('utf-8'))

    def do_GET(self):
        if self.path.rstrip('/') == '/v1/models':
            # OpenAI Models Endpoint
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            
            display_name = "wiki-agent"
            
            response_data = {
                "object": "list",
                "data": [{
                    "id": display_name,
                    "object": "model",
                    "created": 1677652288,
                    "owned_by": "off-grid-agent"
                }]
            }
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'running', 'service': 'Wiki Agent API'}).encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Wiki Agent OpenAI API Running</h1><p>Endpoint: http://localhost:8002/v1/chat/completions</p><p>Authentication: NONE (open)</p></body></html>")

def run_server():
    # Initialize Wiki Agent Backend
    print("[Server] Initializing Wiki Agent Backend...")
    wiki_agent.detect_and_configure_backend()
    
    # Initialize ZIM archive
    zim = wiki_agent.get_zim_archive()
    if zim:
        print("[Server] ZIM Archive loaded successfully.")
    else:
        print("[Server] WARNING: ZIM Archive could not be loaded.")

    print(f"[Server] Starting Wiki Agent OpenAI-Compatible API on port {PORT}...")
    print(f"         Endpoint: http://localhost:{PORT}/v1/chat/completions")
    
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    
    # Use ThreadingTCPServer for concurrent requests + cancellation checks
    with socketserver.ThreadingTCPServer(("", PORT), WikiAgentHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Server] Shutting down...")
            httpd.server_close()

if __name__ == "__main__":
    run_server()
