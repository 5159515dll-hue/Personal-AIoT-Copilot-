export const DASHBOARD_SESSION_COOKIE = "aiot_dashboard_session";
export const DEFAULT_DASHBOARD_ACCESS_CODE = "admin123";

export const protectedDashboardRoutes = [
  "/dashboard",
  "/spaces",
  "/trends",
  "/devices",
  "/hardware",
  "/agent",
  "/models",
  "/rules",
  "/evaluation",
  "/audit"
];

export function dashboardAccessCode(): string {
  return DEFAULT_DASHBOARD_ACCESS_CODE;
}

export function isDashboardAuthEnabled(): boolean {
  return true;
}

export function isProtectedDashboardPath(pathname: string): boolean {
  return protectedDashboardRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export function safeNextPath(value: FormDataEntryValue | string | null | undefined): string {
  const raw = typeof value === "string" ? value : "";
  if (!raw.startsWith("/") || raw.startsWith("//")) {
    return "/dashboard";
  }
  const pathname = raw.split("?")[0] || "/dashboard";
  return isProtectedDashboardPath(pathname) ? raw : "/dashboard";
}

export function publicBaseUrl(headers: Headers, fallbackUrl: string): string {
  const fallback = new URL(fallbackUrl);
  const host = headers.get("x-forwarded-host") ?? headers.get("host") ?? fallback.host;
  const protocol = headers.get("x-forwarded-proto") ?? fallback.protocol.replace(":", "");
  return `${protocol}://${host}`;
}

export async function sessionTokenFor(accessCode: string): Promise<string> {
  const secret = process.env.DASHBOARD_SESSION_SECRET?.trim() || "personal-aiot-copilot-dashboard";
  const bytes = new TextEncoder().encode(`aiot-copilot:${secret}:${accessCode}`);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
