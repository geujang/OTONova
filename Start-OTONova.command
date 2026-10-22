#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -x .venv/bin/python3 ]; then
    exec .venv/bin/python3 -B mac_entry.py "$@"
fi
exec python3 -B mac_entry.py "$@"
