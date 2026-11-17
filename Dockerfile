FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SCOREUP_DB=/data/scoreup.db \
    SCOREUP_DATA_DIR=/data \
    QREADER_WEIGHTS_DIR=/opt/qreader-models \
    YOLO_CONFIG_DIR=/tmp/scoreup-yolo

WORKDIR /app
COPY requirements.txt requirements-docker.txt requirements-qr.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends libzbar0 libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-docker.txt \
    && groupadd --gid 10001 scoreup \
    && useradd --uid 10001 --gid scoreup --no-create-home scoreup \
    && mkdir -p /data/uploads \
    && chown -R scoreup:scoreup /data

COPY app.py calc.py data.py persist.py qr_reader.py ./
RUN python -c "from qr_reader import get_reader; get_reader()"
COPY templates/ ./templates/
COPY static/ ./static/
COPY docker/start.py ./docker/start.py
RUN ln -s /data/uploads /app/static/uploads

USER scoreup
EXPOSE 5000
CMD ["python", "docker/start.py"]
