"""Yanshee 连接配置模板。

使用：
    cp config.example.py config.py
然后编辑 config.py 填入真实值。config.py 已被根 .gitignore 忽略，不会进 Git。

所有值都支持用环境变量覆盖，方便在机器人上用 systemd / shell 注入，
避免把令牌写进文件。

注意：Yanshee 树莓派为 Python 3.5，本工作区脚本须 3.5 兼容（勿用 f-string / future annotations）。
"""
import os

# 机器人内置树莓派的局域网 IP（必填）。
# 来源：Yanshee App → 设置(Setup) → 机器人信息(Robot Information) → IP Address
ROBOT_IP = os.getenv("YANSHEE_ROBOT_IP", "192.168.1.100")

# ——以下仅 bridge/yanshee_agent.py 接入平台时需要——

# 平台 API 基址（默认指向生产服务器；本地联调用 http://127.0.0.1:8000）
AIOT_API_BASE_URL = os.getenv("AIOT_API_BASE_URL", "http://82.157.148.249")

# 内部服务令牌：来自服务器 /home/ubuntu/aiot-copilot/.dashboard-env 的
# AIOT_INTERNAL_API_TOKEN。切勿提交到 Git，建议用环境变量注入。
AIOT_INTERNAL_API_TOKEN = os.getenv("AIOT_INTERNAL_API_TOKEN", "")

# 设备在平台中的稳定身份，遵循 <平台>_<用途>_<序号> 规范。
DEVICE_ID = os.getenv("AIOT_DEVICE_ID", "yanshee_robot_01")
DEVICE_NAME = os.getenv("AIOT_DEVICE_NAME", "Yanshee 人形机器人")

# 设备心跳间隔（秒）：companion_agent.py 定期上报，让机器人保持在设备界面"在线"（offline 阈值约 180s）。
HEARTBEAT_INTERVAL = int(os.getenv("AIOT_HEARTBEAT_INTERVAL", "45"))

# ——情绪采集（perception/capture.py）——
# 机器人所属空间；需先在 /spaces 把该空间的 camera + emotion_recognition 开成 local_only（双门控）。
SPACE_ID = os.getenv("AIOT_SPACE_ID", "space_study_001")
# 设备令牌（在 /devices 为本设备生成）；情绪/事件上报用它，避免把内部服务令牌烧进终端。
DEVICE_TOKEN = os.getenv("AIOT_DEVICE_TOKEN", "")

# ——MQTT 陪伴指令通道（companion_agent.py 订阅 → 做手势/说话）——
# 与服务器同一个鉴权 broker（用户 aiot，密码在服务器 .dashboard-env）。
MQTT_BROKER_HOST = os.getenv("AIOT_MQTT_HOST", "82.157.148.249")
MQTT_BROKER_PORT = int(os.getenv("AIOT_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("AIOT_MQTT_USERNAME", "aiot")
MQTT_PASSWORD = os.getenv("AIOT_MQTT_PASSWORD", "")  # 勿提交；用环境变量或在 config.py 填
MQTT_CLIENT_ID = os.getenv("AIOT_MQTT_CLIENT_ID", "yanshee-companion-agent")
COMMAND_TOPIC = os.getenv("COMPANION_COMMAND_TOPIC", "aiot/companion/command")

# 抽象手势 → 机器人可播放动作名。注意：sync_play_motion 只认 get_motion_list 的 **hts 动作**
# （RaiseRightHand/Hug/Victory…）；layers 动作（H_Wave_R/Hd_* 等）会报 103 找不到。--list 查真实名细调。
GESTURE_MOTION_MAP = {
    "wave": "RaiseRightHand",
    "reach_out": "Hug",
    "tilt_head": "RaiseRightHand",
    "nod": "Victory",
    "idle_nod": "Victory",
    "lean_back": "Victory",
}

# 结束动作：每次手势后保持几秒再回到初始姿态（避免手举着不放）。设 RESET_MOTION=None 可关闭。
RESET_MOTION = os.getenv("AIOT_RESET_MOTION", "Reset")
RESET_AFTER_SECONDS = int(os.getenv("AIOT_RESET_AFTER_SECONDS", "5"))

# ——实时画面（MJPEG 中继直播）——
# open_vision_stream 在机器人本机 :8000/stream.mjpg 发布 MJPEG（multipart/x-mixed-replace）；
# agent 逐帧扫出 JPEG 出站推到服务器，浏览器在 /vision 轮询最新帧（NAT 后出站推送是唯一可达路径）。
LIVE_LOCAL_MJPEG_URL = os.getenv("AIOT_LIVE_MJPEG_URL", "http://127.0.0.1:8000/stream.mjpg")
LIVE_RESOLUTION = os.getenv("AIOT_LIVE_RESOLUTION", "640x480")
LIVE_TARGET_FPS = float(os.getenv("AIOT_LIVE_FPS", "5"))           # 限速丢帧，控带宽/CPU
LIVE_IDLE_TIMEOUT = float(os.getenv("AIOT_LIVE_IDLE_TIMEOUT", "60"))  # 浏览器停发心跳后自动停的秒数

# ——语音输入（Step 3：直接和机器人对话）——
# 开启后机器人持续听写（sync_do_voice_iat_value）→ 送服务器生成回复 → 本机朗读+手势。
# 浏览器输入照常保留。设 AIOT_VOICE_INPUT=0 可关闭（如嫌一直开麦）。
VOICE_INPUT_ENABLED = os.getenv("AIOT_VOICE_INPUT", "1") not in ("0", "false", "False", "")
