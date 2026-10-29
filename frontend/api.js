// 백엔드 API 호출 모음. 화면 코드는 이 파일의 함수만 사용하고 URL·HTTP 세부사항은 모른다.
// (DB에는 직접 접근하지 않는다. 데이터는 항상 /api 를 거친다.)

export const UNASSIGNED = "unassigned";

async function request(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(errorMessage(data) || `요청 실패 (HTTP ${res.status})`);
  }
  return data;
}

function errorMessage(data) {
  if (!data) return "";
  if (typeof data.detail === "string") return data.detail;
  // FastAPI 입력 검증 오류(422)는 detail 이 배열이다.
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(", ");
  return "";
}

export const api = {
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
