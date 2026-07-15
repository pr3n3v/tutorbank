#!/usr/bin/env python3
"""TutorBank ingestion pipeline (M1 — skeleton only for now).

parse files -> extract questions -> DeepSeek generate -> verify -> render diagrams -> insert.

Runs locally on the Mac. Writes to Supabase with the service-role key from ../.env.
See CLAUDE.md §5 (generation), §6 (diagrams), §9 (build order).
"""

import argparse
import json
import sys
from pathlib import Path

# Model ids live in ONE place (CLAUDE.md §5): the shared models.json that the
# Edge Functions also import.
_MODELS = json.loads(
    (Path(__file__).resolve().parent.parent
     / "backend" / "supabase" / "functions" / "_shared" / "models.json").read_text()
)
DEEPSEEK_BASE_URL = _MODELS["base_url"]
MODEL_GENERATE = _MODELS["accurate"]  # generation + cross-model verification

WATCH_PNG_SIZE = (368, 448)  # SE 3 44 mm; render DOT at 2x (736x896) and downscale


def main() -> int:
    parser = argparse.ArgumentParser(description="TutorBank ingestion pipeline")
    parser.add_argument("files", nargs="*", help="assignment PDFs/photos (default: samples/)")
    parser.add_argument("--subject", help="subject code: FLAT|JAVA|AJAVA|EM2|DAA")
    parser.add_argument("--dry-run", action="store_true", help="parse + extract only, no API calls")
    args = parser.parse_args()

    print("M1 not built yet — see CLAUDE.md §9. Blocked on samples upload + M0 schema.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
