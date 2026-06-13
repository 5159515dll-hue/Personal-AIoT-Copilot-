import { NextRequest, NextResponse } from "next/server";
import {
  DASHBOARD_SESSION_COOKIE,
  dashboardAccessCode,
  isProtectedDashboardPath,
  publicBaseUrl,
  sessionTokenFor
} from "./lib/auth";

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!isProtectedDashboardPath(pathname)) {
    return NextResponse.next();
  }

  const accessCode = dashboardAccessCode();
  if (!accessCode) {
    return NextResponse.next();
  }

  const expectedToken = await sessionTokenFor(accessCode);
  const currentToken = request.cookies.get(DASHBOARD_SESSION_COOKIE)?.value;
  if (currentToken === expectedToken) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/access", publicBaseUrl(request.headers, request.url));
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/dashboard/:path*", "/spaces/:path*", "/trends/:path*", "/devices/:path*", "/vision/:path*", "/hardware/:path*", "/emotion/:path*", "/models/:path*", "/rules/:path*", "/evaluation/:path*", "/audit/:path*"]
};
