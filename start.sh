#!/bin/bash
if [ ! -f "/usr/src/app/QmsgNtClient-NapCatQQ/config/napcat.json" ]; then
    mv /tmp/QmsgNtClient-NapCatQQ/config/* /usr/src/app/QmsgNtClient-NapCatQQ/config/ && rm -rf /tmp/QmsgNtClient-NapCatQQ
fi
chmod -R 777 /usr/src/app/QmsgNtClient-NapCatQQ/
Xvfb :1 -screen 0 1080x760x16 +extension GLX +render &
export FFMPEG_PATH=/usr/bin/ffmpeg
export DISPLAY=:1
qq --no-sandbox -q $ACCOUNT