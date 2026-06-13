"""Yanshee 连接配置模板。

使用：
    cp config.example.py config.py
然后编辑 config.py 填入真实值。config.py 已被根 .gitignore 忽略，不会进 Git。

所有值都支持用环境变量覆盖，方便在机器人上用 systemd / shell 注入，
避免把令牌写进文件。
"""
from __future__ import annotations

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
