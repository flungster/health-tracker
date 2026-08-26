/** Thin fetch wrapper: the only place that talks to the network. */

import { getAuthToken } from "../auth/storage";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: string[];

  constructor(status: number, code: string, message: string, details: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  json?: unknown;
  formData?: FormData;
};

async function parseError(response: Response): Promise<ApiError> {
  let code = "ERROR";
  let message = `Request failed (HTTP ${response.status})`;
  let details: string[] = [];
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; details?: string[] };
      detail?: string | Array<{ msg?: string }>;
    };
    if (body.error !== undefined) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      details = body.error.details ?? [];
    } else if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      const first = body.detail[0];
      message = first !== undefined && first.msg !== undefined ? first.msg : message;
    }
  } catch {
    // Non-JSON error body: keep the generic message.
  }
  return new ApiError(response.status, code, message, details);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};
  const token = getAuthToken();
  if (token !== null) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.formData !== undefined) {
    body = options.formData;
  }
  const response = await fetch(path, { method, headers, body });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
