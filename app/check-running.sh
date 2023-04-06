#!/bin/sh
if [ "$(cat /app/health)" -eq 1 ]; then
  exit 1
fi
exit 0