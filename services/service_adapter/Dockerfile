FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl netcat-openbsd && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY adapter_rest.py .

EXPOSE 5001

CMD ["python", "adapter_rest.py"]
