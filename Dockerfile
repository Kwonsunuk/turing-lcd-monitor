FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN pip install pyserial psutil Pillow
COPY monitor.py /app/monitor.py
CMD ["python3", "-u", "/app/monitor.py"]
