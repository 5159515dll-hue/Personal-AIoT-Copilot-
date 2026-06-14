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

# 抽象手势 → 机器人内置动作名（务必用 get_motion_list() 实测的真实名；仅原地安全动作）。
GESTURE_MOTION_MAP = {
    "wave": "H_Wave_R",
    "reach_out": "H_Rise_B",
    "tilt_head": "Hd_SwivelH",
    "nod": "Hd_Wacth_F",
    "idle_nod": "Hd_Wacth_F",
    "lean_back": "H_Str_B",
}
