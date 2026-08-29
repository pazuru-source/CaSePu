#!/usr/bin/env python
"""
Entry point for running the CaSePu Flask application.
"""
import os
from app import create_app

if __name__ == '__main__':
    env = os.getenv('FLASK_ENV', 'development')
    app = create_app(env)

    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"Starting CaSePu on {host}:{port} (env: {env})")
    app.run(host=host, port=port, debug=debug)
