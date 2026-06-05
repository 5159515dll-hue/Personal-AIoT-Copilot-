# systemd 生产服务

这个目录保存 IP 直连服务器部署使用的 systemd 模板。当前服务器路径约定为 `/home/ubuntu/aiot-copilot`，运行用户为 `ubuntu`。

## 服务清单

- `aiot-api.service`：FastAPI 后端，只监听 `127.0.0.1:8000`。
- `aiot-web.service`：Next.js 前端，只监听 `127.0.0.1:3000`，由同源 `/api/*` 代理访问后端。
- `aiot-mqtt-ingestor.service`：MQTT 遥测入站服务，订阅本机 Mosquitto 并写入 PostgreSQL / TimescaleDB。

访问口令固定为 `admin123`，代码不会从 `.dashboard-env` 读取 `DASHBOARD_ACCESS_CODE`。`.dashboard-env` 只保存会话密钥、内部服务令牌、数据库和 MQTT 参数。

## 首次安装

```bash
cd /home/ubuntu/aiot-copilot
sudo cp infra/systemd/aiot-api.service /etc/systemd/system/aiot-api.service
sudo cp infra/systemd/aiot-web.service /etc/systemd/system/aiot-web.service
sudo cp infra/systemd/aiot-mqtt-ingestor.service /etc/systemd/system/aiot-mqtt-ingestor.service
sudo systemctl daemon-reload
sudo systemctl enable --now aiot-api aiot-web
sudo systemctl enable --now aiot-mqtt-ingestor
```

如果暂时没有真实 MQTT 入站需求，可以只启用 `aiot-api` 和 `aiot-web`。

## 更新后重启

```bash
cd /home/ubuntu/aiot-copilot
npm --workspace apps/web run build
sudo systemctl restart aiot-api aiot-web aiot-mqtt-ingestor
systemctl status aiot-api aiot-web aiot-mqtt-ingestor --no-pager
```

## 验证

```bash
npm run smoke:server
npm run eval:agent-safety
```

如果系统没有通过 Nginx 或其他反向代理暴露 80 端口，可以把 `WEB_BASE_URL` 指向 `http://82.157.148.249:3000`。
