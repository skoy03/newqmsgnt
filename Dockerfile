FROM registry.cn-guangzhou.aliyuncs.com/qmsgnt/node:20.12
MAINTAINER DIEYI from NapCatQQ
# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV ACCOUNT=
RUN echo 'sslverify=false' >> /etc/dnf/dnf.conf
COPY sources.list /etc/yum.repos.d/
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# 使用dnf安装软件包
RUN dnf install -y \
    nss \
    libnotify \
    libsecret \
    gbm \
    alsa-lib \
    wqy-zenhei-fonts \
    gnutls \
    glib2-devel \
    dbus-libs \
    gtk3 \
    libXScrnSaver \
    libXtst \
    at-spi2-core \
    libX11-xcb \
    ffmpeg \
    unzip \
    openbox \
    xorg-x11-server-Xorg \
    dbus-user-session \
    xorg-x11-server-Xvfb \
    supervisor \
    xdg-utils \
    git \
    fluxbox \
    curl && \
    dnf clean all && \
    rm -rf /var/cache/dnf /tmp/* /var/tmp/*

WORKDIR /usr/src/app

RUN curl -L -o /tmp/QmsgNtClient-NapCatQQ.zip https://gh-proxy.com/github.com/1244453393/QmsgNtClient-NapCatQQ/releases/download/v$(curl https://fastly.jsdelivr.net/gh/1244453393/QmsgNtClient-NapCatQQ@main/package.json | grep '"version":' | sed -E 's/.*([0-9]{1,}\.[0-9]{1,}\.[0-9]{1,}).*/\1/')/QmsgNtClient-NapCatQQ.zip

RUN unzip -o /tmp/QmsgNtClient-NapCatQQ.zip -d ./QmsgNtClient-NapCatQQ
RUN unzip -o /tmp/QmsgNtClient-NapCatQQ.zip -d /tmp/QmsgNtClient-NapCatQQ

COPY start.sh ./start.sh

RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/amd64/) && \
    curl -o linuxqq.deb https://dldir1.qq.com/qqfile/qq/QQNT/a5519e17/linuxqq_3.2.15-31363_${arch}.rpm && \
    dpkg -i --force-depends linuxqq.rpm && rm linuxqq.rpm && \
    chmod +x start.sh && \
    echo "(async () => {await import('file:///usr/src/app/QmsgNtClient-NapCatQQ/napcat.mjs');})();" > /opt/QQ/resources/app/loadNapCat.js && \
    sed -i 's|"main": "[^"]*"|"main": "./loadNapCat.js"|' /opt/QQ/resources/app/package.json

RUN cd ./QmsgNtClient-NapCatQQ && npm config set registry https://registry.npmmirror.com/ && npm i

VOLUME /usr/src/app/QmsgNtClient-NapCatQQ/config
VOLUME /usr/src/app/QmsgNtClient-NapCatQQ/logs
VOLUME /root/.config/QQ

EXPOSE 6099

ENTRYPOINT ["bash", "start.sh"]
