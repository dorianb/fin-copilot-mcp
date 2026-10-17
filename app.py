"""Entry point for Hugging Face Spaces.

HF Spaces runs `python <app_file>` from /app with only requirements.txt
installed. The `screener` package lives under src/ (src-layout), so it is not
on sys.path by default. Add it before importing.

Exposing `demo` at module level lets HF's Gradio hot-reload manage the
Blocks lifecycle; calling `demo.launch()` in __main__ starts the server.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import gradio as gr

from screener.server import build_demo

demo = build_demo()

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), mcp_server=True)
