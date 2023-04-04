# Terrorzone Discord Webhook

used to write information about the currently active terrorzone in D2:R into a discord channel.

## Requirements

- to use the prebuilt `.pex` file a system is needed with python3.10 installed
- to use the `tdw-start.sh` bash script a unix system with bash and python3.10 installed is needed
- to build the `.pex` file yourself you also need to have `pip` installed. 

## Build pex file

- Optional, use virtual interpreter
    ```commandline
    pip install --user virtualenv
    virtualenv .venv
    source .venv/bin/activate
    ```
- execute: `pip install pex`
- navigate to the project folder and then execute:
    ```commandline
    pex . -r requirements.txt -c main.py -o terrorzone-discord-webhook.pex
    ```

## Usage


- Go to your Discord server settings
- Go to Apps > Integrations
- Go to Webhooks and create a new webhook
- Choose the channel you want it to post updates in
- Copy the webhook link
- The webhook link looks like this.
    ```url
    https://discord.com/api/webhooks/{id}/{token}
    ```
- (modify the webhook name and icon)

### Adapt .env file (or create environment variables)

- create the file `.env` in the `data` directory
- the content of the file should look like this:
    ```commandline
    # .env
    WEBHOOK_ID='{id}'
    WEBHOOK_TOKEN='{token}'
    ENDPOINT_TZ='https://d2runewizard.com/api/terror-zone'
    ENDPOINT_TOKEN=''
    ```
- replace `{id}` and `{token}` with the information from the discord webhook link
- (ENDPOINT_TOKEN is currently not required)

### Run pex file

- move the `terrorzone-discord-webhook.pex` file, `tdw-start.sh` file and the `data` folder to the place from where you want to execute it
  - make sure that at least `tdw-start.sh` is executable (`chmod +x tdw-start.sh`)
- recommended way: use the bash script to start the pex file. It helps (but not completely avoids) with double execution and path problems
  ```bash
  cd /script/path/location
  ./tdw-start.sh
  
  # or
  
  /script/path/location/tdw-start.sh 
  ```
  - arguments can be added the same way as using the `.pex` file directly (a bit further down in the README)
    ```bash
    /script/path/location/tdw-start.sh LOG_TO_CONSOLE=1 FORCE_INITIAL_ANNOUNCEMENT=1 {...}
    ``` 
- run with default values (/path/to/script is required): 
    ```bash
    ./terrorzone-discord-webhook.pex /path/to/script
    ```
- run with arguments to overwrite default values (/path/to/script is required):: 
    ```bash
    ./terrorzone-discord-webhook.pex /path/to/script LOG_TO_CONSOLE=1 FORCE_INITIAL_ANNOUNCEMENT=1 {...}
    ```
  - Allowed arguments:   
    ```
    FORCE_INITIAL_ANNOUNCEMENT={0, 1}
    LOG_TO_CONSOLE={0, 1}
    LOG_PATH=/path/to/log
    LOG_LEVEL={DEBUG, INFO, WARNING, ERROR, CRITICAL}
    ```

### Running hints

- (if using a raspberry pi) install python3.10 (see links)
  - fix link problems after installation:
    ```bash
    cd /usr/bin && sudo mv python3 python3_old && sudo ln -s python3.9 python3
    ```
  - to keep the process running either use a systemd service or execute via ssh (or others like cron)
    - ssh: `ssh {HostFromSSHConfig} /script/path/location/tdw-start.sh`
    - systemd service (create service, start service now and enable it so that it can start automatically):
      ```bash
      sudo sh -c "cat > /etc/systemd/system/terrorzone-discord-webhook.service" << EOF
      [Unit]
      Description=Systemd service for starting terrorzone discord webhook at startup
      [Service]
      ExecStart=/bin/bash /path/to/tdw-start.sh
      Restart=on-failure
      [Install]
      WantedBy=default.target
      EOF
      sudo systemctl start terrorzone-discord-webhook.service
      sudo systemctl enable terrorzone-discord-webhook.service
      ```
- if the pid (the number) in the log file changes without script restart, you have 2 instances running.
  - (`logs/.lock` should show the most recent used pid)
  - kill one of them with `kill -9 {pid}`

## Links

- https://d2runewizard.com/integration
- https://itheo.tech/installing-python-310-on-raspberry-pi

### Pex usage

- http://connor-johnson.com/2014/12/17/working-with-python-pex-files/
- https://www.shearn89.com/2021/04/15/pex-file-creation

### discord-webhook

- https://pypi.org/project/discord-webhook/
- https://github.com/lovvskillz/python-discord-webhook
