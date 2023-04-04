# Terrorzone Discord Webhook

used to write information about the currently active terrorzone in D2:R into a discord channel.

Based on https://d2runewizard.com/integration

## Requirements

- docker: https://docs.docker.com/engine/install/
    - or rootless docker: https://docs.docker.com/engine/security/rootless/
- discord server with a webhook: https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
- token for the d2runewizard.com TZ API: https://d2runewizard.com/profile/T41jagcO0UcTLKJiC5UOmDCdGtS2

## Preparation 

- crate a `.env` file (use `.env-example` as base)
    - The webhook link looks like this.
        ```url
        https://discord.com/api/webhooks/{id}/{token}
        ```
- (optional) create folder(s) for `logs` and `zone-info.json`
    - the used folder(s) require access right for anybody when the `nobody` user is used to run the container 
        ```
        chmod -R 777 /your/path
        ```

### Build docker image

https://docs.docker.com/build/building/packaging/

example:
```
docker build -t d2r-terrorzones:<tag> .
```

## Run/initialize docker container

https://docs.docker.com/engine/reference/commandline/run/

example:
```
docker run \
 --name d2r-terrorzones \
 --restart=unless-stopped \
 --env LOG_LEVEL='DEBUG' \
 --env-file='/home/docker-user/Documents/scm/TerrorZones-Discord/.env' \
 --mount type=bind,source="/home/docker-user/Documents/data/terrorzone",target="/logs" \
 --mount type=bind,source="/home/docker-user/Documents/data/terrorzone",target="/zone-info" \
 --user "nobody" \
 d2r-terrorzones:<tag>
```
or
```
docker run \
 --name d2r-terrorzones \
 --restart=unless-stopped \
 --env-file='/home/docker-user/Documents/scm/TerrorZones-Discord/.env' \
 --user "nobody" \
 d2r-terrorzones:<tag>
```
> without `/logs` mount, logs will be written to stdout

> without `/zone-info` mount (or when zone-info.json is missing), file included in image will be used

## Misc
- The following environemt variables can be passed to the docker container:
    - LOG_LEVEL - optional - {INFO, WARNING, ERROR, CRITICAL} (everything else defaults to DEBUG)
    - WEBHOOK_ID - required - id from your discord webhook
    - WEBHOOK_TOKEN - required - token from your discord webhook
    - ENDPOINT_TZ - optional - defaults to https://d2runewizard.com/api/terror-zone
    - ENDPOINT_TOKEN - required - personalized token from https://d2runewizard.com/profile/T41jagcO0UcTLKJiC5UOmDCdGtS2
    - CONTACT - required - email addresse
    - PLATFORM - required - other communication method information like Discord, Whatsapp, ...
    - PUBLIC_REPO - required - link to your public repo
- when an accesible `\logs` mount is created, log files will be written into this folder. Otherwise they are written to stdout
- when an accesible `\zone-info` mount is created, zone-info.json in this directory is preferred instead of the build in one.
- docker start: `docker start d2r-terrorzones`
- docker stop: `docker stop d2r-terrorzones`
- docker remove (i.e. to run/initialize again)): `docker rm d2r-terrorzones`
