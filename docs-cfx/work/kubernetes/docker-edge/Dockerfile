FROM ubuntu
RUN apt-get update
RUN apt-get install -y curl
COPY .crossbar /
COPY crossbarfx /
RUN chmod a+x /crossbarfx
ENTRYPOINT ["./crossbarfx", "edge", "start"]
