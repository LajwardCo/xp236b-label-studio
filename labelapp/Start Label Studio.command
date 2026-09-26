#!/bin/bash
cd "$(dirname "$0")"
# reuse if already running, else start
curl -s -o /dev/null http://127.0.0.1:8236/ || (python3 server.py >/tmp/labelapp.log 2>&1 &)
sleep 1
open "http://127.0.0.1:8236/"
