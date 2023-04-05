# syntax=docker/dockerfile:1

# TODO: limit cpu/ram
# TODO: Volume?

FROM python:3-alpine

# install app dependencies
COPY requirements.txt .

# install app
COPY zone-info.json .
COPY check-running.sh /bin/check-running.sh
COPY main.py .

# configure system
RUN pip install --no-cache-dir -r requirements.txt \
    ; mkdir /app \
    ; mkdir /app/logs \
    ; mkdir /app/zone-info \
    ; chmod 777 /bin/check-running.sh \
    ; echo -n 0 > /app/health \
    ; chmod 666 /app/health \
    ; mv zone-info.json /app/ \
    ; chmod 444 /app/zone-info.json \
    ; mv main.py /app/ \
    ; chmod 444 /app/main.py \
    ; rm /requirements.txt \
    ; passwd -l root

WORKDIR /app

USER nobody

HEALTHCHECK --interval=5m --timeout=3s \
    CMD ["sh", "-c", "/bin/check-running.sh"]

# final configuration
ENTRYPOINT [ "python", "main.py" ]
#CMD ["sh", "-c", "ls -la"]