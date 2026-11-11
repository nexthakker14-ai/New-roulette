FROM ossrs/srs:5

USER root
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/local/srs
COPY roulette.conf ./conf/roulette.conf
COPY bridge.py ./bridge.py
EXPOSE 1935/tcp 1985/tcp 8080/tcp

CMD ["sh", "-c", "./objs/srs -c conf/roulette.conf & python3 -u ./bridge.py"]
