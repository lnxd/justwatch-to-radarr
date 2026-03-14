FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY justwatch_to_radarr.py .

USER 1000
CMD ["python", "justwatch_to_radarr.py"]
