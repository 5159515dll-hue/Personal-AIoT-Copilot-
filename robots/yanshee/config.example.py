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

# ——实时画面（真·MJPEG 流式中继，30fps）——
# 用树莓派官方 raspivid 直驱 CSI 摄像头出 MJPEG（YanAPI 流被限在 ~10fps，绕不过），
# agent 包成 multipart 经一条长连接 chunked POST 推到服务器，浏览器 <img> 直接渲染。
# 直播期间 raspivid 独占摄像头（YanAPI 拍照/人脸暂不可同时用），停播即释放。
LIVE_WIDTH = int(os.getenv("AIOT_LIVE_WIDTH", "640"))
LIVE_HEIGHT = int(os.getenv("AIOT_LIVE_HEIGHT", "480"))
LIVE_FPS = int(os.getenv("AIOT_LIVE_FPS", "30"))
LIVE_IDLE_TIMEOUT = float(os.getenv("AIOT_LIVE_IDLE_TIMEOUT", "60"))  # 浏览器停发心跳后自动停的秒数
# 注：本机 raspivid 不支持 -q（MJPEG 质量），帧约 40-50KB；若上行带宽不足想省流量，
# 把 AIOT_LIVE_WIDTH/HEIGHT 调小（如 480x360）即可，帧率不变。

# ——语音对话（Step 3：唤醒触发，不再一直听）——
# 喊两次唤醒词 → 听写 → 服务器流式回复（大模型→逐句火山TTS）→ mpg123 边收边播（≤3s 开口）。
# 浏览器输入照常保留。设 AIOT_VOICE_INPUT=0 关闭语音对话。
VOICE_INPUT_ENABLED = os.getenv("AIOT_VOICE_INPUT", "1") not in ("0", "false", "False", "")
WAKE_WORDS = ["小暖", "小暖小暖", "你好小暖", "小暖在吗"]   # 离线命令词唤醒
WAKE_HITS = int(os.getenv("AIOT_WAKE_HITS", "2"))            # 窗口内喊到几次才唤醒（降误触发；嫌难触发可设 1）
WAKE_WINDOW = float(os.getenv("AIOT_WAKE_WINDOW", "8"))       # 计数窗口秒数
MAX_CONV_TURNS = int(os.getenv("AIOT_MAX_CONV_TURNS", "3"))   # 唤醒后最多连续对话轮数
