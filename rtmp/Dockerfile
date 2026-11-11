FROM ossrs/srs:5

WORKDIR /usr/local/srs
COPY roulette.conf ./conf/roulette.conf
EXPOSE 1935/tcp 1985/tcp 8080/tcp

CMD ["./objs/srs", "-c", "conf/roulette.conf"]
