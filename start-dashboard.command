#!/bin/bash
# Double-click this file to start the TutorBank dashboard.
# It opens http://127.0.0.1:8765 in your browser.
# Keep this window open while you use it; close it (or press Ctrl-C) to stop.

PORT=8765
DIR="/Users/pr3n3v/watch/ingestion"
URL="http://127.0.0.1:${PORT}"

cd "$DIR" || {
  echo "❌ Can't find the ingestion folder: $DIR"
  read -n1 -s -p "Press any key to close…"; exit 1
}

# Already running? Don't crash on the busy port — just open the browser to it.
if curl -s -o /dev/null --max-time 2 "$URL"; then
  echo "✅ Dashboard is already running — opening it in your browser."
  open "$URL"
  exit 0
fi

# A dead process still holding the port? Clear it so we can start clean.
STALE=$(lsof -ti tcp:${PORT} 2>/dev/null)
if [ -n "$STALE" ]; then
  echo "Clearing a stuck process on port ${PORT}…"
  kill -9 $STALE 2>/dev/null; sleep 1
fi

PY="$(command -v python3 || echo /usr/bin/python3)"
echo "Starting TutorBank dashboard at ${URL} …"
echo "(Keep this window open. Close it or press Ctrl-C to stop.)"
echo
"$PY" dashboard.py
STATUS=$?

# If it fell over, keep the window up so you can actually read why.
if [ $STATUS -ne 0 ] && [ $STATUS -ne 130 ]; then
  echo
  echo "⚠️  The dashboard exited with an error (code $STATUS) — see the messages above."
  read -n1 -s -p "Press any key to close this window…"
fi
