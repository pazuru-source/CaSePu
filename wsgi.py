"""
WSGI entry point for production deployment.
Use with Gunicorn or other WSGI application servers.

Example:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
"""
import os
from app import create_app

env = os.getenv('FLASK_ENV', 'production')
app = create_app(env)

if __name__ == '__main__':
    app.run()
