FROM ubuntu
RUN apt-get update
RUN apt-get install -y curl
RUN mkdir /.crossbar
COPY crossbarfx /
COPY crossbarfx-ui.zip /.crossbar/.crossbarfx-ui.zip
RUN chmod a+x crossbarfx
EXPOSE 443
ENTRYPOINT ["./crossbarfx", "master", "start"]
