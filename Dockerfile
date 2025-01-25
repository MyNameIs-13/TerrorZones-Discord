# TODO: apply chmod outside of Dockerfile
# TODO: upload image to a registry
FROM docker.io/python:3.13.1-alpine3.21

WORKDIR /app

COPY app/ .

RUN pip install --no-cache-dir -r /app/requirements.txt \
  ; mkdir /app/logs \
  ; mkdir /app/zone-info \
  ; chmod 0555 /app/check-running.sh \
  ; chmod 0444 /app/zone-info.json \
  ; chmod 0444 /app/main.py

#  watchtower should not try to monitor and update
LABEL com.centurylinklabs.watchtower.enable="false"

HEALTHCHECK --interval=5m --timeout=3s \
    CMD ["sh", "-c", "/app/check-running.sh"]

ENTRYPOINT [ "python", "main.py" ]