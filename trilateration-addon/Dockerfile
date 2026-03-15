FROM python:3.11-alpine

RUN apk add --no-cache gcc musl-dev python3-dev openblas-dev gfortran

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY trilaterate.py .
COPY server.py .

EXPOSE 8099

CMD ["python3", "server.py"]
```

**`requirements.txt`:**
```
paho-mqtt==1.6.1
aiohttp==3.9.5
numpy==1.26.4
scipy==1.13.1
