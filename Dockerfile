FROM python:3.10-slim as base

FROM base as app
WORKDIR auspak-backend
COPY . .
CMD pip install -r requirements.txt && \
    python app.py --port $AUSPAK_PORT
