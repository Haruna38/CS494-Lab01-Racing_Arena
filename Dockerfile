FROM ubuntu:latest
WORKDIR /app
COPY . .
RUN apt update && \
	apt install -y python3 python3-pip && \
	pip3 install -r requirements.txt

# Server socket port
ENV GAME_SERVER_PORT 4000

# Client site port
ENV GAME_CLIENT_PORT 1275

CMD ["python3", "./main.py"]

EXPOSE ${GAME_CLIENT_PORT} ${GAME_SERVER_PORT}