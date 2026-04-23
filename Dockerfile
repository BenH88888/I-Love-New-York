# Stage 1: Build React frontend
FROM node:20 AS frontend-build

WORKDIR /app/frontend

ARG VITE_GOOGLE_MAPS_API_KEY
ARG VITE_GOOGLE_MAP_ID

ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY
ENV VITE_GOOGLE_MAP_ID=$VITE_GOOGLE_MAP_ID

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./

RUN npm run build

# Stage 2: Install Python deps
FROM python:3.10-slim AS python-deps

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"


# Stage 3: Final runtime image
FROM python:3.10-slim

ENV CONTAINER_HOME=/var/www

WORKDIR $CONTAINER_HOME

COPY --from=python-deps /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=python-deps /root/.cache/huggingface /root/.cache/huggingface

COPY src/ $CONTAINER_HOME/src/
COPY --from=frontend-build /app/frontend/dist $CONTAINER_HOME/frontend/dist

CMD ["python", "-m", "gunicorn", "--chdir", "src", "app:app", "--bind", "0.0.0.0:5000", "--log-level", "debug"]
