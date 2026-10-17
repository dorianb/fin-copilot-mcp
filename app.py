"""Entry point for Hugging Face Spaces.

HF Spaces runs `python <app_file>` from /app with only requirements.txt
installed. The `screener` package lives under src/ (src-layout), so it is not
on sys.path by default. Add it before importing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from screener.server import main

if __name__ == "__main__":
    main()
