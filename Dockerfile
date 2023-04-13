# TODO: apply chmod outside of Dockerfile
# TODO: upload image to a registry
FROM docker.io/python:3.11-alpine3.17

WORKDIR /app

COPY app/ .

RUN pip install --no-cache-dir -r /app/requirements.txt \
  ; mkdir /app/logs \
  ; mkdir /app/zone-info \
  ; chmod 0555 /app/check-running.sh \
  ; chmod 0444 /app/zone-info.json \
  ; chmod 0444 /app/main.py

HEALTHCHECK --interval=5m --timeout=3s \
    CMD ["sh", "-c", "/app/check-running.sh"]

ENTRYPOINT [ "python", "main.py" ]