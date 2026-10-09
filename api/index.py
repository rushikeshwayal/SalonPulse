"""Vercel serverless entrypoint for the FastAPI application."""
from backend.app.main import app

# Vercel's Python runtime serves this ASGI application.
