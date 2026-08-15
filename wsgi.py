# -*- coding: utf-8 -*-
"""Production WSGI entry point (no SSL — nginx handles HTTPS)."""
from app import app, init_db

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
