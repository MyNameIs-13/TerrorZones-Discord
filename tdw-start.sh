#!/bin/bash

SCRIPT_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # workaround because I have no clue how to get the path in python

# very silly approach to try and reduce double execution
old_pid="$(cat "${SCRIPT_HOME}"/logs/.lock)"
running_pids_count="$(ps -ef | grep -c "${old_pid}.*/usr/bin/python3.*/home/skodo/.pex")"
if (( "${running_pids_count}" > 1 )); then
  kill -SIGINT "${old_pid}" # SIGTERM seems to hard kill python on linux (finally is not executed)
  echo "killed ${old_pid}"
  sleep 5 # give the process time to terminate  
fi
rm "${SCRIPT_HOME}/logs/.lock"

# finally execute the python program
chmod +x "${SCRIPT_HOME}/terrorzone-discord-webhook.pex"
"${SCRIPT_HOME}/terrorzone-discord-webhook.pex" "${SCRIPT_HOME}" "$@"