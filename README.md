# Terrorzone Discord Webhook

used to write information about the currently active terrorzone in D2:R into a discord channel.

Based on https://d2runewizard.com/integration

## Requirements

- docker: https://docs.docker.com/engine/install/
    - or rootless docker: https://docs.docker.com/engine/security/rootless/
- docker compose: https://docs.docker.com/compose/install/
- discord server with a webhook: https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
- token for the d2runewizard.com TZ API: https://d2runewizard.com/profile/T41jagcO0UcTLKJiC5UOmDCdGtS2

## Preparation 

- crate a `.secrets` file (use `.secrets-example` as base)
    - The webhook link looks like this.
        ```url
        https://discord.com/api/webhooks/{id}/{token}
        ```
- (optional) create folder(s) for `logs` and `zone-info.json` and add them to the `.env` file
    - the used folder(s) require access right for anybody when the `nobody` user is used to run the container 
        ```
        chmod -R 666 /your/path
        ```

### Build & run docker container

```
docker compose up
```

## Misc

- The following environment variables can be passed to the docker container:
    - LOG_LEVEL - optional - {INFO, WARNING, ERROR, CRITICAL} (everything else defaults to DEBUG)
    - WEBHOOK_ID - required - id from your discord webhook
    - WEBHOOK_TOKEN - required - token from your discord webhook
    - ENDPOINT_TOKEN - required - personalized token from https://d2runewizard.com/profile/T41jagcO0UcTLKJiC5UOmDCdGtS2
    - CONTACT - required - email address
    - PLATFORM - required - other communication method information like Discord, Whatsapp, ...
    - PUBLIC_REPO - required - link to your public repo
- when an accessible `/app/logs` mount is created, log files will be written into this folder. Otherwise they are written to stdout
- when an accessible `/app/zone-info` mount is created, zone-info.json in this directory is preferred instead of the build in one.
- some systems don't support cpus limit, comment-out the limit in `docker-compose.yml`