import { NextRequest, NextResponse } from "next/server";
import { DASHBOARD_SESSION_COOKIE } from "@/lib/auth";

export function GET(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/access?status=logged_out", request.url));
  response.cookies.set({
    name: DASHBOARD_SESSION_COOKIE,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.DASHBOARD_COOKIE_SECURE === "true",
    path: "/",
    maxAge: 0
  });
  return response;
}
