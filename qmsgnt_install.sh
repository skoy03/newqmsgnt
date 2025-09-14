WEBUI_PORT=6099
ACCOUNT=1244453393
docker build -t qmsgnt -f Dockerfile .
sudo docker run --restart=always -d --name qmsgnt -e ACCOUNT=$ACCOUNT -p $WEBUI_PORT:6099 -v ${PWD}/QQ:/root/.config/QQ -v ${PWD}/config:/usr/src/app/QmsgNtClient-NapCatQQ/config -v ${PWD}/logs:/usr/src/app/QmsgNtClient-NapCatQQ/logs qmsgnt