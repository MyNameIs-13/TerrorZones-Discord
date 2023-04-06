# syntax=docker/dockerfile:1

FROM python:3-alpine

WORKDIR /app

# add app files
COPY app/ .

# configure system
RUN pip install --no-cache-dir -r /app/requirements.txt \
    ; rm /app/requirements.txt \
    ; mkdir /app/logs \
    ; mkdir /app/zone-info \
    ; chmod 777 /app/check-running.sh \
    ; printf '0' > /app/health \
    ; chmod 666 /app/health \
    ; chmod 444 /app/zone-info.json \
    ; chmod 444 /app/main.py \
    ; passwd -l root

USER nobody

HEALTHCHECK --interval=5m --timeout=3s \
    CMD ["sh", "-c", "/app/check-running.sh"]

# final configuration
ENTRYPOINT [ "python", "main.py" ]
