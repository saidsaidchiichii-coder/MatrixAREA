#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
pip install -q -r requirements.txt
: "${GEMINI_API_KEY:?Set GEMINI_API_KEY first}"
python backend/main.py
