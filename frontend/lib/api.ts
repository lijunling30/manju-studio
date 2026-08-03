/* REST API 客户端：统一鉴权、错误处理、闸口响应透传 */

const TOKEN_KEY = 'manju_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers, cache: 'no-store' });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
      window.location.href = '/login';
    }
    throw new ApiError(401, '登录已过期，请重新登录');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown, query?: string) =>
    request<T>(`${path}${query ? `?${query}` : ''}`, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),
};

/** 媒体 URL：后端静态资产经 Next 代理 */
export function assetUrl(rel: string): string {
  if (!rel) return '';
  if (rel.startsWith('http')) return rel;
  return `/storage/${rel.replace(/^storage\//, '')}`;
}

/** 每次会话唯一 ID（确认闸口会话级开关） */
export function sessionId(): string {
  if (typeof window === 'undefined') return '';
  let sid = sessionStorage.getItem('manju_session');
  if (!sid) {
    sid = `web_${Math.random().toString(36).slice(2, 10)}`;
    sessionStorage.setItem('manju_session', sid);
  }
  return sid;
}
