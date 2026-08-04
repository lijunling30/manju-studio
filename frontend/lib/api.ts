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
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

/** 媒体 URL：后端静态资产经 Next 代理（/storage/* → backend /storage/*） */
export function assetUrl(rel: string): string {
  if (!rel) return '';
  if (rel.startsWith('http')) return rel;
  // 后端 save_bytes 已返回 /storage/xxx 格式，直接使用，避免双重前缀
  if (rel.startsWith('/storage/')) return rel;
  // 兜底：不带前缀的相对路径补上 /storage/
  return `/storage/${rel.replace(/^\/+/, '')}`;
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

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * 轮询任务中心直至指定任务完成。
 * 异步任务（小说/剧本/分镜/关键帧/角色/视频/音频/成片）在后台执行，
 * 生成后必须轮询到 success 再刷新数据，否则界面表现为「无响应、图不出现」。
 */
export async function waitForTask(
  taskId: number,
  kind?: string,
  intervalMs = 2000,
  timeoutMs = 15 * 60 * 1000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await sleep(intervalMs);
    const tasks = await api.get<Array<{ id: number; kind: string; status: string; error?: string }>>('/api/tasks');
    const t = tasks.find((x) => x.id === taskId && (!kind || x.kind === kind));
    if (!t) continue;
    if (t.status === 'success' || t.status === 'completed') return;
    if (t.status === 'failed' || t.status === 'manual_review' || t.status === 'cancelled') {
      throw new ApiError(500, t.error || `任务失败（${t.status}）`);
    }
  }
  throw new ApiError(500, '任务执行超时，请稍后在任务中心查看');
}
