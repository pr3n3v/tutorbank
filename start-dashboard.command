#!/bin/bash
# Double-click this file (Finder) to start the TutorBank dashboard.
# It opens http://127.0.0.1:8765 in your browser. Close this window (or press
# Ctrl-C) to stop the server.
cd /Users/pr3n3v/watch/ingestion || { echo "ingestion folder not found"; exit 1; }
echo "Starting TutorBank dashboard…  (close this window to stop)"
echo
exec python3 dashboard.py
