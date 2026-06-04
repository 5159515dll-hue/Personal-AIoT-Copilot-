import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

type ApiProxyContext = {
  params: Promise<{ path: string[] }>;
};

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade"
]);

export async function GET(request: NextRequest, context: ApiProxyContext) {
  return proxyApiRequest(request, context);
}

export async function POST(request: NextRequest, context: ApiProxyContext) {
  return proxyApiRequest(request, context);
}

export async function PUT(request: NextRequest, context: ApiProxyContext) {
  return proxyApiRequest(request, context);
}

export async function PATCH(request: NextRequest, context: ApiProxyContext) {
  return proxyApiRequest(request, context);
}

export async function DELETE(request: NextRequest, context: ApiProxyContext) {
  return proxyApiRequest(request, context);
}

async function proxyApiRequest(request: NextRequest, context: ApiProxyContext): Promise<Response> {
  const { path } = await context.params;
  const target = apiTargetUrl(path, request.nextUrl.search);
  const headers = proxyRequestHeaders(request);
  const body = await proxyRequestBody(request);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual"
    });
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: proxyResponseHeaders(upstream.headers)
    });
  } catch {
    return Response.json(
      { detail: "后端 API 代理失败，请检查 FastAPI 服务、API_BASE_URL 和服务器网络。" },
      { status: 502 }
    );
  }
}

function apiTargetUrl(path: string[], search: string): string {
  const base = configured(process.env.API_BASE_URL) ?? configured(process.env.NEXT_PUBLIC_API_BASE_URL) ?? "http://localhost:8000";
  const url = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, base);
  url.search = search;
  return url.toString();
}

function proxyRequestHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  const cookie = request.headers.get("cookie");
  const internalToken = configured(process.env.AIOT_INTERNAL_API_TOKEN);

  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (accept) {
    headers.set("accept", accept);
  }
  if (cookie) {
    headers.set("cookie", cookie);
  }
  if (internalToken) {
    headers.set("X-AIoT-Internal-Token", internalToken);
  }
  return headers;
}

async function proxyRequestBody(request: NextRequest): Promise<ArrayBuffer | undefined> {
  if (request.method === "GET" || request.method === "HEAD") {
    return undefined;
  }
  return request.arrayBuffer();
}

function proxyResponseHeaders(upstreamHeaders: Headers): Headers {
  const headers = new Headers();
  upstreamHeaders.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  return headers;
}

function configured(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed.replace(/\/$/, "") : null;
}
