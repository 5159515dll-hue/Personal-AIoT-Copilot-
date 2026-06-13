# Yanshee 人形机器人接入说明

把 UBTECH Yanshee 人形机器人接入个人空间智能物联助手平台的开发文档。整体分两个阶段：**先让机器人动起来 + 配好二次开发环境**，再把它作为一个新设备类型接入平台。

> 安全前提：机器人会**物理移动**，是高风险执行器。本文所有控制相关能力都必须经过平台 `policy.py` 策略引擎和审计，默认只读，不允许智能体直接驱动机器人运动。

## 1. 机器人是什么

Yanshee 本质是**一个会动的树莓派**：

| 部件 | 说明 |
|---|---|
| 主控 | 内置 Raspberry Pi 3B/3B+，跑 Raspbian（Debian Linux） |
| 运动 | 17 个舵机驱动关节（双臂、双腿、头部） |
| 感知 | 8MP 摄像头、麦克风阵列、扬声器、IMU（陀螺仪/加速度计）、可扩展环境传感器 |
| 扩展 | GPIO、USB、HDMI、POGO 接口 |
| 网络 | WiFi（先 AP 热点配网，再加入家庭 WiFi） |

因为内部是标准 Linux + 树莓派，它能直接复用本平台已有的树莓派网关接入范式（`examples/raspberry-pi-gateway/aiot_gateway.py`）和 `aiot.v1` 协议，**不需要为它定制新接口**。

## 2. 二次开发接口（支持，且是核心定位）

Yanshee 是开源开发平台，提供三层接口：

1. **RESTful API**（HTTP，跨语言）—— 覆盖运动控制、设备控制、机器视觉、语音识别、模型识别/训练。**这是平台后端集成的天然入口**。
2. **yanapi**（最新 Pythonic SDK）—— 跑在机器人内置树莓派上，自带 JupyterLab IDE 和大量例程。入口：`YanAPI.yan_api_init("<robot-ip>")`。
3. **旧版 SDK**（`Yanshee-Raspi-SDK`，C/Python，已停维护）、Blockly/Scratch（教育用）。

支持语言：Python、C/C++、Java、Blockly/Scratch。新项目走 **yanapi（机上脚本）+ RESTful API（平台集成）** 两条线。

## 3. 接入前准备：让它动起来

按顺序做，拿到机器人 IP 是后续所有开发的前提：

1. **充电、开机**（长按开关，等启动提示音/灯）。
2. **手机装 Yanshee App**（iOS/Android）→ 先连机器人热点 → 把机器人配到家庭 WiFi。
3. **在 App 里跑内置动作**（打招呼、太极等）+ **做一次舵机校准**——这是最快的"动起来"验证。
4. **记录机器人 IP**：App → 设置 (Setup) → 机器人信息 (Robot Information) → IP Address。

拿到 IP 后打开开发通道：

```bash
# SSH 进机器人内置树莓派（默认账号 pi / 密码 raspberry —— 上线前务必改密码）
ssh pi@<robot-ip>

# JupyterLab：浏览器开机器人 IP（v2.2+ 预装，自带运动/视觉/语音例程）

# 从开发机传代码到机器人
scp robots/yanshee/scripts/first_motion.py pi@<robot-ip>:/home/pi/
```

```python
# 最小运动示例（函数名取自官方 YanAPI 2.0.0 接口文档）
import YanAPI
YanAPI.yan_api_init("<robot-ip>")
motions = YanAPI.get_motion_list()        # 先查内置动作名，不要凭空猜
YanAPI.sync_play_motion(name="<取自上一步>", direction="", speed="normal", repeat=1)
```

> 函数名以**官方 YanAPI 2.0.0 接口文档**为准（接口表：ubtrobot-new.oss-cn-shenzhen.aliyuncs.com/static/MINI/Yanshee/yanapi/html-zh/YansheeSDK.html）；内置**动作名**用 `get_motion_list()` 查，**不要硬编码捏造**。`robots/yanshee/scripts/connect_check.py` 会打印机器人上实际可用的 API。

## 4. 本仓库工作区结构

```text
robots/yanshee/
├── README.md            工作区上手说明
├── requirements.txt     依赖（yanapi、requests）
├── config.example.py    连接配置模板（复制为 config.py 后填真实值；config.py 不入库）
├── scripts/
│   ├── connect_check.py 连通性检查 + yanapi API 自省（动起来前先跑这个）
│   ├── first_motion.py  第一个运动控制脚本
│   └── read_sensors.py  读电量 / 环境传感器 / IMU 遥测
└── bridge/
    └── yanshee_agent.py 把机器人作为【只读设备】接入平台（仿 aiot_gateway.py）
```

机器人侧脚本（`scripts/`、`bridge/`）设计为在机器人内置树莓派上运行；`config.py` 和设备令牌不提交到 Git。

## 5. 接入 AIoT Copilot 架构

复用平台现有的 `aiot.v1` 设备连接协议（见 `docs/device-connection-interface.md`），分两半：

### 5.1 只读遥测桥接（第一阶段，安全）

机器人上跑 `bridge/yanshee_agent.py`，用 yanapi 读真实数据，按 `aiot.v1` 推给平台，让机器人作为一个**只读设备**出现在 `/devices`：

```text
Yanshee(树莓派) --yanapi读数--> yanshee_agent.py --HTTP aiot.v1--> 平台 /api/device-connections/*
```

- `device_id`：`yanshee_robot_01`（遵循 `<平台>_<用途>_<序号>` 规范）。
- `device_type`：`yanshee`，`transport`：`http`，`protocol_version`：`aiot.v1`。
- **注册** `POST /api/device-connections/register`：声明能力（电量、姿态、IMU、视觉事件）。新设备进注册表即 `risk_level=read_only`、`controllable=false`。
- **心跳** `POST /api/device-connections/{id}/heartbeat`：带 `battery_percent`、在线状态。
- **遥测** `POST /api/device-connections/{id}/telemetry`：电量、关节温度、IMU 等 readings。
- **视觉事件** `POST /api/device-connections/{id}/events`：摄像头边缘识别结果（人/物体），不传原始图像进 readings；图片走 `/media`，需先在 `/spaces` 开启 `local_only` 媒体策略。

这一阶段机器人**只上报、不接受控制**，零物理风险，是接入的第一个里程碑。

### 5.2 受控运动（第二阶段，高风险，策略门控）

把"让机器人做某个动作"接成一条**独立的控制链路**，与遥测分离：

- 控制能力由**服务端人工配置**到设备注册表（不能靠自注册获得），风险等级按物理动作定为 `medium`/`high`。
- 每次动作请求经 `policy.py`：高风险拒绝、中风险要求**显式确认**、记录审计日志、做速率限制（防连续误触）。
- 平台侧新增一个 Yanshee 控制适配器，把已确认的动作翻译成机器人 RESTful API 调用（运动控制接口）。
- 提示注入、"忽略安全策略"等文本永远不能提升控制权限（`policy.py` 已有的注入检测）。

对齐平台现有的设备风险模型（`docs/safety-policy.md`）：门锁/报警器/强电是 `forbidden`，机器人运动同属需要严格门控的物理执行能力。

## 6. 分阶段路线

1. **动起来**：App 配网 → 内置动作 → 拿 IP →（开发机）`connect_check.py` 跑通。✅ 第一步
2. **会编程**：SSH/JupyterLab → `first_motion.py`、`read_sensors.py` 跑通，摸清 yanapi。
3. **进平台（只读）**：机上跑 `yanshee_agent.py`，机器人作为只读设备出现在 `/devices`，电量/姿态进遥测。
4. **受控动作**：服务端配置控制能力 + 策略确认 + 审计，平台可下发"挥手/前进"等已确认动作。
5. **融合智能体**：智能体读机器人状态、在策略允许下建议/触发动作；视觉事件接入异常事件流。

## 7. 参考资料

- 官方开发者站（需注册）：https://yandev.ubtrobot.com/
- 官方文档 / Q&A：https://docs.ubtrobot.com/yanshee/
- GitHub SDK：https://github.com/UBTEDU/Yanshee-SDK 、https://github.com/UBTEDU/Yanshee-Raspi-SDK 、https://github.com/UBTEDU/YanShee-SDK-DEMO
- 平台设备协议：`docs/device-connection-interface.md`、`docs/safety-policy.md`、`docs/media-streaming.md`
- 接入范例：`examples/raspberry-pi-gateway/aiot_gateway.py`
