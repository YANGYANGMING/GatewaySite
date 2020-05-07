var gws;
var WebSocketServer = require('ws').Server,
    wss = new WebSocketServer({ port: 9000 });
wss.on('connection', function (ws) {
    gws = ws;
    console.log('client connected');
    ws.on('message', function (message) {
        console.log(message);
        setInterval(show,5000);//每隔5秒 服务端向浏览器 推送消息

    });
});

function show()
{
    gws.send(1122);
}