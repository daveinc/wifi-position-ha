FROM python:3.11-alpine

RUN apk add --no-cache gcc musl-dev python3-dev openblas-dev gfortran

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY trilaterate.py .
COPY server.py .

EXPOSE 8099

CMD ["python3", "server.py"]
