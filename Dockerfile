FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ engine/
COPY main.py .

RUN mkdir -p /app/data

CMD ["python", "main.py"]
