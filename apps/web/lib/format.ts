export function formatTime(value: string): string {
  const parts = shanghaiDateParts(value);
  if (!parts) return "时间未知";
  return `${pad2(parts.hour)}:${pad2(parts.minute)}`;
}

export function formatDateTime(value: string): string {
  const parts = shanghaiDateParts(value);
  if (!parts) return "时间未知";
  return `${pad2(parts.month)}月${pad2(parts.day)}日 ${pad2(parts.hour)}:${pad2(parts.minute)}`;
}

const SHANGHAI_OFFSET_MS = 8 * 60 * 60 * 1000;

function shanghaiDateParts(value: string): { month: number; day: number; hour: number; minute: number } | null {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return null;
  const shifted = new Date(timestamp + SHANGHAI_OFFSET_MS);
  return {
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes()
  };
}

function pad2(value: number): string {
  return value.toString().padStart(2, "0");
}

export function titleCase(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function metricLabel(value: string): string {
  const labels: Record<string, string> = {
    temperature: "温度",
    humidity: "湿度",
    co2: "二氧化碳",
    light: "光照",
    presence: "有人状态",
    noise: "噪声"
  };
  return labels[value] ?? value;
}

export function riskLabel(value: string): string {
  const labels: Record<string, string> = {
    read_only: "只读",
    low: "低风险",
    medium: "中风险",
    high: "高风险",
    forbidden: "禁止控制"
  };
  return labels[value] ?? value;
}

export function statusLabel(value: string): string {
  const labels: Record<string, string> = {
    good: "良好",
    watch: "关注",
    poor: "较差",
    ok: "正常",
    stale: "过期",
    anomaly: "异常",
    online: "在线",
    offline: "离线",
    unknown: "未知",
    unavailable: "不可用",
    success: "成功",
    blocked: "已阻止",
    requires_confirmation: "需要确认",
    failed: "失败",
    allowed: "允许",
    denied: "拒绝",
    user: "用户",
    agent: "智能体",
    system: "系统"
  };
  return labels[value] ?? titleCase(value);
}

export function deviceTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    esp32_sensor_node: "传感器节点",
    smart_light: "智能灯",
    ir_remote: "红外遥控",
    smart_plug: "智能插座",
    safety_alarm: "安全报警器"
  };
  return labels[value] ?? value;
}

export function locationLabel(value: string): string {
  const labels: Record<string, string> = {
    desk: "书桌",
    shelf: "书架",
    floor: "地面",
    wall: "墙面",
    ceiling: "天花板"
  };
  return labels[value] ?? value;
}

export function applianceLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    led_lamp: "发光二极管台灯",
    led_strip: "发光二极管灯带",
    fan: "风扇",
    unknown: "未知",
    "未知": "未知"
  };
  if (!value) return "无";
  return labels[value] ?? value;
}

export function translatedState(state: Record<string, unknown>): Record<string, unknown> {
  const keyLabels: Record<string, string> = {
    sampling_interval_seconds: "采样间隔秒数",
    battery: "电量",
    power: "电源",
    brightness: "亮度",
    mode: "模式",
    muted: "是否静音",
    self_test: "自检"
  };
  const valueLabels: Record<string, string> = {
    on: "开启",
    off: "关闭",
    natural: "自然风",
    ok: "正常"
  };
  return Object.fromEntries(
    Object.entries(state).map(([key, value]) => [
      keyLabels[key] ?? key,
      typeof value === "string" ? valueLabels[value] ?? value : value
    ])
  );
}
