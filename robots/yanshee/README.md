# Yanshee 机器人工作区

UBTECH Yanshee 人形机器人的二次开发与平台接入工作区。完整设计见 [`docs/yanshee-integration.md`](../../docs/yanshee-integration.md)。

> ⚠️ 机器人会**物理移动**。运行任何运动脚本前，请清空机器人周围空间、扶稳机器人、远离桌子边缘。

## 目录

```text
robots/yanshee/
├── requirements.txt     依赖（yanapi、requests）
├── config.example.py    连接配置模板 → 复制为 config.py 填真实值（config.py 不入库）
├── scripts/
│   ├── connect_check.py 连通性检查 + yanapi API 自省（第一步先跑这个）
│   ├── first_motion.py  第一个运动控制脚本
│   └── read_sensors.py  读电量 / 环境传感器 / IMU
└── bridge/
    └── yanshee_agent.py 把机器人作为【只读设备】接入平台
```

## 上手步骤

1. **配网拿 IP**：用 Yanshee App 把机器人连上 WiFi，记下 IP（App → 设置 → 机器人信息 → IP Address）。

2. **填配置**：
   ```bash
   cd robots/yanshee
   cp config.example.py config.py
   # 编辑 config.py，把 ROBOT_IP 改成机器人实际 IP
   ```

3. **装依赖**（在哪台机器跑脚本就在哪台装）：
   ```bash
   pip install -r requirements.txt
   ```
   yanapi 通常已**预装在机器人内置树莓派上**。若在开发机上 `pip install yanapi` 失败，就把脚本 `scp` 到机器人上、SSH 进去运行。

4. **先验连通性 + 摸清 API**：
   ```bash
   python scripts/connect_check.py
   ```
   它会探测机器人端口、连接 yanapi、并**打印机器人上实际可用的 yanapi 函数列表**——后续脚本以这个列表为准。

5. **让它动**：
   ```bash
   python scripts/first_motion.py        # 播放一个内置动作
   python scripts/read_sensors.py        # 读电量/传感器/IMU
   ```

6. **接入平台（只读）**：在机器人上运行
   ```bash
   AIOT_INTERNAL_API_TOKEN="<服务器内部令牌>" python bridge/yanshee_agent.py
   ```
   机器人会作为只读设备出现在平台 `/devices`，电量与姿态进入遥测。

## 在哪台机器运行？

- `scripts/*` 和 `bridge/yanshee_agent.py` 依赖 yanapi 读真实硬件数据 → **在机器人内置树莓派上运行**最稳。
- yanapi 底层是机器人的 RESTful API，理论上也能从同网段开发机远程调用；以 `connect_check.py` 的探测结果为准。

## 注意

- `config.py`、设备令牌、内部服务令牌**不要提交 Git**（已在根 `.gitignore` 忽略 `config.py`）。
- 机器人默认 SSH 账号 `pi/raspberry` 是公开默认值，正式使用前**务必改密码**。
- 脚本里的 yanapi 函数名取自**官方 YanAPI 2.0.0 接口文档**（接口表 ubtrobot-new.oss-cn-shenzhen.aliyuncs.com/static/MINI/Yanshee/yanapi/html-zh/YansheeSDK.html），不要凭空捏造。内置**动作名**用 `get_motion_list()` 查；`connect_check.py` 会打印机器人上实际可用的 API。
