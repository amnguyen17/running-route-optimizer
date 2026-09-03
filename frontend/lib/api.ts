import type { GeneratedRoute, RouteRequest, SavedRouteDetail, SavedRouteSummary } from "@/types/route";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiRequestError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });

  if (!response.ok) {
    const body = await safeJson(response);
    const detail = extractDetail(body) ?? `Request failed with status ${response.status}`;
    throw new ApiRequestError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

export async function generateRoute(request: RouteRequest): Promise<GeneratedRoute> {
  return apiFetch<GeneratedRoute>("/routes/generate", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function saveRoute(request: RouteRequest): Promise<SavedRouteDetail> {
  return apiFetch<SavedRouteDetail>("/saved-routes", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function listSavedRoutes(favoritesOnly = false): Promise<SavedRouteSummary[]> {
  const query = favoritesOnly ? "?favorites_only=true" : "";
  return apiFetch<SavedRouteSummary[]>(`/saved-routes${query}`);
}

export async function getSavedRoute(id: number): Promise<SavedRouteDetail> {
  return apiFetch<SavedRouteDetail>(`/saved-routes/${id}`);
}

export async function deleteSavedRoute(id: number): Promise<void> {
  await apiFetch<void>(`/saved-routes/${id}`, { method: "DELETE" });
}

export async function setRouteFavorite(id: number, isFavorite: boolean): Promise<SavedRouteSummary> {
  return apiFetch<SavedRouteSummary>(`/saved-routes/${id}/favorite`, {
    method: "PATCH",
    body: JSON.stringify({ is_favorite: isFavorite }),
  });
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
