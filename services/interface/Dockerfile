FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl netcat-openbsd && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY index.html .
COPY script.js .
COPY style.css .

EXPOSE 5000

CMD ["python", "app.py"]
