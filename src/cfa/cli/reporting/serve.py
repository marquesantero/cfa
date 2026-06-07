"""cfa serve — live metrics/health server."""

from __future__ import annotations


def cmd_serve(args) -> int:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from cfa.observability.metrics import get_metrics_text

    port = args.port or 8765

    if args.metrics_port:
        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/metrics":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(get_metrics_text().encode())
                elif self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
        threading.Thread(target=lambda: HTTPServer(("", args.metrics_port), MetricsHandler).serve_forever(), daemon=True).start()
        print(f"Metrics endpoint at http://localhost:{args.metrics_port}/metrics")
        print(f"Health  endpoint at http://localhost:{args.metrics_port}/health")

    print(f"Serving at http://localhost:{port}/")
    print("Note: Dashboard uses live metrics only. No synthetic data is generated.")
    print("Use cfa report dashboard --audit-file <file> for an HTML dashboard report.")

    class PingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK\n")
            elif self.path == "/metrics":
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(get_metrics_text().encode())
            else:
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(b"CFA v0.1.6 -- See /health and /metrics\n")

    HTTPServer(("", port), PingHandler).serve_forever()
    return 0
