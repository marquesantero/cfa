"""cfa serve — live metrics/health server with lifecycle dashboard."""

from __future__ import annotations


_LIFECYCLE_HTML = (
    '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CFA Lifecycle Dashboard</title>'
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>'
    '<style>body{font-family:system-ui;margin:2rem;background:#111;color:#eee}'
    'h1{color:#4fc3f7}.card{background:#1e1e1e;border-radius:8px;padding:1rem;margin:1rem 0}'
    '.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}'
    '.metric{background:#263238;border-radius:6px;padding:1rem;text-align:center}'
    '.metric .value{font-size:2rem;font-weight:bold}.metric .label{font-size:.8rem;color:#888;margin-top:.5rem}'
    '.good{color:#66bb6a}.warn{color:#ffa726}.bad{color:#ef5350}'
    '.chart-wrap{max-width:800px;margin:1rem auto}</style></head><body>'
    '<h1>CFA Lifecycle Dashboard</h1><div class="metrics">'
    '<div class="metric"><div class="value good" id="ifo">--</div><div class="label">IFo (Operational)</div></div>'
    '<div class="metric"><div class="value good" id="ifs">--</div><div class="label">IFs (Semantic)</div></div>'
    '<div class="metric"><div class="value good" id="ifg">--</div><div class="label">IFg (Governance)</div></div>'
    '<div class="metric"><div class="value good" id="idi">--</div><div class="label">IDI (Drift)</div></div>'
    '</div><div class="chart-wrap"><canvas id="trendChart"></canvas></div>'
    '<div class="chart-wrap"><canvas id="costChart"></canvas></div>'
    '<script>async function refresh(){try{let r=await fetch("/metrics");let t=await r.text();'
    'document.getElementById("ifo").textContent=(t.match(/cfa_lifecycle_ifo ([\\d.]+)/)||["","--"])[1];'
    'document.getElementById("ifs").textContent=(t.match(/cfa_lifecycle_ifs ([\\d.]+)/)||["","--"])[1];'
    'document.getElementById("ifg").textContent=(t.match(/cfa_lifecycle_ifg ([\\d.]+)/)||["","--"])[1];'
    'document.getElementById("idi").textContent=(t.match(/cfa_lifecycle_idi ([\\d.]+)/)||["","--"])[1];'
    '}catch(e){};}refresh();setInterval(refresh,10000);</script></body></html>'
)


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
        print(f"Metrics: http://localhost:{args.metrics_port}/metrics")
        print(f"Health:  http://localhost:{args.metrics_port}/health")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK\n")
            elif self.path == "/metrics":
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(get_metrics_text().encode())
            elif self.path in ("/", "/dashboard"):
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(_LIFECYCLE_HTML.encode())
            else:
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(b"CFA v1.0.0 -- /health /metrics /dashboard\n")

    print(f"CFA serve at http://localhost:{port}/")
    print(f"  /             Lifecycle dashboard (HTML)")
    print(f"  /dashboard    Lifecycle dashboard (HTML)")
    print(f"  /health       Health check")
    print(f"  /metrics      Prometheus metrics")
    HTTPServer(("", port), Handler).serve_forever()
    return 0
