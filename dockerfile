# syntax=docker/dockerfile:1
FROM python:3-alpine

# install app dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# configure system
RUN addgroup -S app && adduser -S app -G app \
    ; mkdir /logs \
    ; mkdir /zone-info \
    ; rm requirements.txt
USER app
WORKDIR /home/app

# install app
COPY zone-info.json .
COPY main.py .

# final configuration
CMD [ "python", "main.py" ]