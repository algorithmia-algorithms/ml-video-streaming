#!/bin/bash
set e
git clone git://github.com/arut/nginx-rtmp-module.git
wget http://nginx.org/download/nginx-1.18.0.tar.gz && \
tar -xf nginx-1.18.0.tar.gz && cd nginx-1.18.0 && \
./configure --with-http_ssl_module --add-module=../nginx-rtmp-module && \
make && make install