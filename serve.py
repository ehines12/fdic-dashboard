#!/usr/bin/env python3
"""Local preview: python3 serve.py  ->  http://localhost:8010 (serves web/)."""
import functools, http.server, os
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
http.server.ThreadingHTTPServer(("127.0.0.1", 8010), functools.partial(http.server.SimpleHTTPRequestHandler, directory=d)).serve_forever()
