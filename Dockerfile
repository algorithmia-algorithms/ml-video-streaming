FROM ubuntu:18.04

RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    python3-pip \
    python3 \
    git \
    wget \
    curl \
    libpcre3 \
    libpcre3-dev \
    libssl-dev \
    zlib1g-dev \
    lsof

RUN add-apt-repository -y ppa:jonathonf/ffmpeg-4 && \
    apt-get update && apt-get install -y ffmpeg

WORKDIR /opt/streaming

COPY build_nginx.sh /opt/streaming/build_nginx.sh
RUN /bin/bash /opt/streaming/build_nginx.sh

COPY requirements.txt /opt/streaming/requirements.txt
RUN pip3 install -r /opt/streaming/requirements.txt
COPY src /opt/streaming/src
COPY init.py /opt/streaming/init.py
COPY src/broadcast/nginx.conf /usr/local/nginx/conf/nginx.conf
COPY config.yaml /opt/streaming/config.yaml

ENTRYPOINT ["/usr/bin/python3", "/opt/streaming/init.py"]