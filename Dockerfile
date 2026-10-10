FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG INSTALL_ARCHIVE_PROBE=false
RUN apt-get update && apt-get upgrade -y && if [ "$INSTALL_ARCHIVE_PROBE" = true ]; then apt-get install -y --no-install-recommends ffmpeg; fi && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip
COPY app ./app
COPY ops/monitor.py /srv/monitor.py
ENV PYTHONPATH=/srv/app HALO_DATA_DIR=/data
RUN groupadd -g 10001 clutchtape && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin clutchtape
USER 10001:10001
EXPOSE 8140
CMD ["python", "/srv/app/main.py"]
