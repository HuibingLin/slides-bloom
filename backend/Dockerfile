FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-math fontconfig fonts-noto-cjk fonts-noto-core fonts-crosextra-carlito \
    fonts-crosextra-caladea fonts-croscore fonts-stix && \
    find /usr/share/fonts/truetype/noto -type f ! -name NotoSansSymbols2-Regular.ttf -delete && \
    fc-cache -f && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data /usr/local/share/fonts/licensed
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
