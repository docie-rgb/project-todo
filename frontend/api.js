// 백엔드 API 호출 모음. 화면 코드는 이 파일의 함수만 사용하고 URL·HTTP 세부사항은 모른다.
// (DB·Supabase 에는 직접 접근하지 않는다. 데이터와 로그인은 항상 /api 를 거친다.)
// 로그인 토큰은 HttpOnly 쿠키에 있어 이 코드에서 읽을 수 없고, 브라우저가 요청에 자동으로 붙인다.

export const UNASSIGNED = "unassigned";

// 세션이 완전히 만료되면 화면에 알린다 (app.js 가 로그인 화면으로 전환).
export const AUTH_REQUIRED_EVENT = "auth-required";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function send(method, path, body) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(errorMessage(data) || `요청 실패 (HTTP ${res.status})`, res.status);
  }
  return data;
}

// 동시에 여러 요청이 401 을 받아도 갱신은 한 번만 한다.
let refreshing = null;
function refreshSession() {
  refreshing ??= send("POST", "/api/auth/refresh").finally(() => { refreshing = null; });
  return refreshing;
}

// 데이터 요청: 401(액세스 토큰 만료)이면 한 번 갱신하고 다시 시도한다.
async function request(method, path, body) {
  try {
    return await send(method, path, body);
  } catch (err) {
    if (err.status !== 401) throw err;
    try {
      await refreshSession();
    } catch {
      window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
      throw new ApiError("로그인이 필요합니다.", 401);
    }
    return send(method, path, body);
  }
}

function errorMessage(data) {
  if (!data) return "";
  if (typeof data.detail === "string") return data.detail;
  // FastAPI 입력 검증 오류(422)는 detail 이 배열이다.
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(", ");
  return "";
}

export const api = {
  // 인증 (응답에 토큰은 없고 이메일만 온다)
  me: () => send("GET", "/api/auth/me"),
  login: (email, password) => send("POST", "/api/auth/login", { email, password }),
  logout: () => send("POST", "/api/auth/logout"),

  listProjects: () => request("GET", "/api/projects"),
  createProject: (name) => request("POST", "/api/projects", { name }),
  renameProject: (id, name) => request("PATCH", `/api/projects/${encodeURIComponent(id)}`, { name }),
  deleteProject: (id) => request("DELETE", `/api/projects/${encodeURIComponent(id)}`),

  listTodos: (project, sort) =>
    request("GET", `/api/todos?project=${encodeURIComponent(project)}&sort=${encodeURIComponent(sort)}`),
  createTodo: (todo) => request("POST", "/api/todos", todo),
  updateTodo: (id, changes) => request("PATCH", `/api/todos/${encodeURIComponent(id)}`, changes),
  deleteTodo: (id) => request("DELETE", `/api/todos/${encodeURIComponent(id)}`),
};
