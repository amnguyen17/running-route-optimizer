import type { GeneratedRoute, RouteRequest } from "@/types/route";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiRequestError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function generateRoute(request: RouteRequest): Promise<GeneratedRoute> {
  const response = await fetch(`${API_BASE_URL}/routes/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const body = await safeJson(response);
    const detail = extractDetail(body) ?? `Request failed with status ${response.status}`;
    throw new ApiRequestError(detail, response.status);
  }

  return response.json();
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function extractDetail(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // FastAPI validation errors return a list of { msg, loc, ... }
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  }
  return null;
}
