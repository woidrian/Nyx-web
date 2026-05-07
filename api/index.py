"""Vercel Serverless Function entry point — re-exports the FastAPI app from server.py.

Vercel detects this file under /api/ and runs it as a Python function.
All requests rewritten to /api/index by vercel.json end up here, and FastAPI
routes them internally based on the original request path.
"""
import sys
from pathlib import Path

# Make project root importable so `from server import app` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app  # noqa: E402

# Expose for Vercel's @vercel/python runtime
__all__ = ["app"]
