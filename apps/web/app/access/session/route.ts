import { NextRequest, NextResponse } from "next/server";
import {
  DASHBOARD_SESSION_COOKIE,
  dashboardAccessCode,
  safeNextPath,
  sessionTokenFor
} from "@/lib/auth";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const nextPath = safeNextPath(formData.get("next"));
  const submittedCode = String(formData.get("code") ?? "").trim();
  const accessCode = dashboardAccessCode();

  if (!accessCode) {
    return redirectToAccess(request, nextPath, "unconfigured");
  }

  if (submittedCode !== accessCode) {
    return redirectToAccess(request, nextPath, "invalid");
  }

  const response = NextResponse.redirect(new URL(nextPath, request.url), { status: 303 });
  response.cookies.set({
    name: DASHBOARD_SESSION_COOKIE,
    value: await sessionTokenFor(accessCode),
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.DASHBOARD_COOKIE_SECURE === "true",
    path: "/",
    maxAge: 60 * 60 * 8
  });
  return response;
}

function redirectToAccess(request: NextRequest, nextPath: string, error: string) {
  const url = new URL("/access", request.url);
  url.searchParams.set("next", nextPath);
  url.searchParams.set("error", error);
  return NextResponse.redirect(url, { status: 303 });
}
