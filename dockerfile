# syntax=docker/dockerfile:1
FROM python:3-alpine

# install app dependencies
COPY requirements.txt .

# configure system
RUN pip install --no-cache-dir -r requirements.txt \
    ; mkdir /app \
    ; mkdir /app/logs \
    ; mkdir /app/zone-info \
    ; echo -n 0 > /app/health \
    ; chmod 666 /app/health \
    ; rm /requirements.txt \
    ; passwd -l root

WORKDIR /app

# install app
COPY --chmod=444 zone-info.json .
COPY --chmod=444 main.py .

USER nobody

HEALTHCHECK --interval=12s --timeout=12s \
    CMD if [[ $(cat health) -eq 1 ]]; then exit 1; fi

# final configuration
ENTRYPOINT [ "python", "main.py" ]
#CMD ["sh", "-c", "ls -la"]