import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const BACKEND_URL = process.env.DEMO2_API_URL || "http://127.0.0.1:8020";
const DEMO2_DIR =
  process.env.DEMO2_DIR ||
  path.resolve(process.cwd(), "../../code/demo2");
const PYTHON_BIN =
  process.env.DEMO2_PYTHON ||
  "/home/rtx/miniconda3/envs/minor/bin/python";

let bootPromise: Promise<boolean> | null = null;

async function isBackendAlive(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    const res = await fetch(`${BACKEND_URL}/api/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

async function ensureBackendRunning(): Promise<boolean> {
  if (await isBackendAlive()) return true;
  if (bootPromise) return bootPromise;

  bootPromise = (async () => {
    try {
      const child = spawn(
        /*turbopackIgnore: true*/ PYTHON_BIN,
        ["-m", "uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", "8020"],
        {
          cwd: DEMO2_DIR,
          detached: true,
          stdio: "ignore",
        }
      );
      child.unref();

      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 500));
        if (await isBackendAlive()) {
          return true;
        }
      }
      return false;
    } catch {
      return false;
    } finally {
      bootPromise = null;
    }
  })();

  return bootPromise;
}

async function proxyRequest(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  // Access request properties immediately so Next.js 16 cacheComponents treats this as dynamic
  const reqUrl = new URL(req.url);
  const { path: segments } = await ctx.params;
  const targetUrl = `${BACKEND_URL}/api/${segments.join("/")}${reqUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  const accept = req.headers.get("accept");
  if (accept) {
    headers.set("accept", accept);
  }

  let bodyBuffer: ArrayBuffer | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    bodyBuffer = await req.arrayBuffer();
  }

  const doFetch = async () =>
    fetch(targetUrl, {
      method: req.method,
      headers,
      body: bodyBuffer ? Buffer.from(bodyBuffer) : undefined,
      cache: "no-store",
    });

  let upstream: Response;
  try {
    upstream = await doFetch();
  } catch {
    const started = await ensureBackendRunning();
    if (!started) {
      return NextResponse.json(
        {
          detail: {
            code: "backend_unavailable",
            message:
              "The Demo 2 Python backend is starting up or unavailable on 127.0.0.1:8020. Please wait a moment and retry.",
          },
        },
        { status: 503 }
      );
    }
    try {
      upstream = await doFetch();
    } catch (err) {
      return NextResponse.json(
        {
          detail: {
            code: "backend_error",
            message: `Failed to reach Demo 2 backend: ${err instanceof Error ? err.message : "unknown error"}`,
          },
        },
        { status: 502 }
      );
    }
  }

  const respHeaders = new Headers();
  const upType = upstream.headers.get("content-type");
  if (upType) respHeaders.set("content-type", upType);
  const upDisp = upstream.headers.get("content-disposition");
  if (upDisp) respHeaders.set("content-disposition", upDisp);
  if (upType && upType.includes("text/event-stream")) {
    respHeaders.set("connection", "keep-alive");
    respHeaders.set("x-accel-buffering", "no");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: respHeaders,
    });
  }

  const data = await upstream.arrayBuffer();
  return new Response(data, {
    status: upstream.status,
    headers: respHeaders,
  });
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(req, ctx);
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(req, ctx);
}

export async function DELETE(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(req, ctx);
}
