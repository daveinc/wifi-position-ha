ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-numpy py3-scipy

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

COPY trilaterate.py .
COPY server.py .
COPY run.sh .

RUN chmod +x run.sh

CMD ["/app/run.sh"]
