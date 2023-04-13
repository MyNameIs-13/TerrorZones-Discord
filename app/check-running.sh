#!/bin/sh
if [ "$(cat /tmp/health)" -eq 1 ]; then
  exit 1
fi
exit 0