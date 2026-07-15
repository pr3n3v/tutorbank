#!/usr/bin/env python3
"""TutorBank ingestion pipeline (M1 — skeleton only for now).

parse files -> extract questions -> DeepSeek generate -> verify -> render diagrams -> insert.

Runs locally on the Mac. Writes to Supabase with the service-role key from ../.env.
See CLAUDE.md §5 (generation), §6 (diagrams), §9 (build order).
"""

import argparse
import sys

# Model names must live in ONE place (CLAUDE.md §5). Verify against DeepSeek docs
# before first generation run — legacy deepseek-chat/-reasoner die 2026-07-24.
MODEL_GENERATE = "deepseek-v4-pro"
MODEL_LIVE = "deepseek-v4-flash"

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
