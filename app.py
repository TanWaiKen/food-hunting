"""Vercel entrypoint (Vercel auto-detects `app` in app.py). Local: uv run uvicorn app:app --reload"""
from foodhunt.web import app  # noqa: F401
