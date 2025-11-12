FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl netcat-openbsd && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service_crud.py .

RUN mkdir -p /app/data

EXPOSE 5002

CMD ["python", "service_crud.py"]
