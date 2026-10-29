// 화면 상태와 렌더링. 데이터는 api.js 를 통해서만 주고받는다.
import { api, AUTH_REQUIRED_EVENT, UNASSIGNED } from "./api.js";

const state = {
  projects: [],
  unassigned: { total_count: 0, done_count: 0 },
  selected: UNASSIGNED, // 프로젝트 ID 또는 UNASSIGNED
  todos: [],
  sort: "created",
  editingTodo: null, // 수정 중인 할 일 ID
  editingProject: null, // 이름 수정 중인 프로젝트 ID
};

// 새로고침해도 마지막으로 보던 프로젝트와 정렬을 유지한다 (편의 기능, 실패해도 무시).
const PREFS_KEY = "project-todo:view";
function loadPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
    if (typeof saved.selected === "string") state.selected = saved.selected;
    if (saved.sort === "due" || saved.sort === "created") state.sort = saved.sort;
  } catch { /* 저장소 사용 불가 시 기본값 */ }
}
function savePrefs() {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify({ selected: state.selected, sort: state.sort }));
  } catch { /* 무시 */ }
}

const $ = (id) => document.getElementById(id);

// textContent 로만 글자를 넣어 사용자가 입력한 HTML이 실행되지 않게 한다.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// ---------- 알림 ----------
let toastTimer;
function showError(err) {
  const toast = $("toast");
  toast.textContent = err instanceof Error ? err.message : String(err);
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
}

// ---------- 날짜 ----------
// "오늘"은 사용자 컴퓨터의 로컬 날짜 (DB_DESIGN: UTC가 아닌 로컬 기준)
function todayLocal() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function isOverdue(todo, today) {
  return !todo.is_done && todo.due_date != null && todo.due_date < today;
}

function dueLabel(dueDate, today) {
  const days = Math.round((Date.parse(dueDate) - Date.parse(today)) / 86400000);
  if (days === 0) return `마감 ${dueDate} (오늘)`;
  if (days < 0) return `마감 ${dueDate} (${-days}일 지남)`;
  return `마감 ${dueDate} (D-${days})`;
}

// ---------- 데이터 불러오기 ----------
function selectedExists() {
  return state.selected === UNASSIGNED || state.projects.some((p) => p.id === state.selected);
}

async function loadProjects() {
  const data = await api.listProjects();
  state.projects = data.projects;
  state.unassigned = data.unassigned;
  if (!selectedExists()) state.selected = UNASSIGNED;
}

async function loadTodos() {
  state.todos = await api.listTodos(state.selected, state.sort);
}

async function refresh() {
  await loadProjects();
  await loadTodos();
  render();
}

// 변경 작업 공통 처리: 실패하면 알림, 성공하면 목록·개수를 다시 불러온다.
async function run(action) {
  try {
    await action();
    await refresh();
    return true;
  } catch (err) {
    showError(err);
    return false;
  }
}

// ---------- 렌더링 ----------
function currentName() {
  if (state.selected === UNASSIGNED) return "미분류";
  return state.projects.find((p) => p.id === state.selected)?.name ?? "미분류";
}

function render() {
  $("current-name").textContent = currentName();
  renderProjects();
  renderProjectOptions($("todo-project"), state.selected === UNASSIGNED ? null : state.selected);
  renderTodos();
}

function renderProjects() {
  const items = [
    projectItem({ id: UNASSIGNED, name: "미분류", ...state.unassigned }, true),
    ...state.projects.map((p) => projectItem(p, false)),
  ];
  $("project-list").replaceChildren(...items);
}

function projectItem(project, isUnassigned) {
  const active = project.id === state.selected;
  const editing = project.id === state.editingProject;
  const classes = ["project-item"];
  if (active) classes.push("active");
  if (isUnassigned) classes.push("unassigned");
  if (editing) classes.push("editing");

  return el(
    "li",
    { class: classes.join(" ") },
    el(
      "button",
      {
        class: "project-select",
        type: "button",
        title: project.name,
        "aria-current": active ? "true" : "false",
        onclick: () => selectProject(project.id),
      },
      el("span", { class: "project-name" }, project.name),
      el("span", { class: "count", title: "완료 / 전체" }, `${project.done_count} / ${project.total_count}`),
    ),
    // 미분류는 실제 프로젝트가 아니므로 이름 수정·삭제가 없다.
    !isUnassigned && !editing && el(
      "span",
      { class: "project-actions" },
      el("button", { class: "link", type: "button", title: "이름 수정", "aria-label": `${project.name} 이름 수정`,
        onclick: () => { state.editingProject = project.id; render(); focusEdit(".project-rename input"); } }, "✎"),
      el("button", { class: "link danger", type: "button", title: "삭제", "aria-label": `${project.name} 삭제`,
        onclick: () => removeProject(project) }, "✕"),
    ),
    editing && projectRenameForm(project),
  );
}

function projectRenameForm(project) {
  const input = el("input", { type: "text", value: project.name, maxLength: 100, "aria-label": "프로젝트 새 이름" });
  const cancel = () => { state.editingProject = null; render(); };
  input.addEventListener("keydown", (e) => { if (e.key === "Escape") cancel(); });
  return el(
    "form",
    {
      class: "project-rename",
      onsubmit: async (e) => {
        e.preventDefault();
        const name = input.value.trim();
        if (!name) return showError("프로젝트 이름을 입력하세요.");
        if (await run(() => api.renameProject(project.id, name))) {
          state.editingProject = null;
          render();
        }
      },
    },
    input,
    el("button", { type: "submit" }, "저장"),
    el("button", { type: "button", onclick: cancel }, "취소"),
  );
}

async function removeProject(project) {
  const msg = `'${project.name}' 프로젝트를 삭제할까요?\n소속 할 일 ${project.total_count}건은 삭제되지 않고 미분류로 이동합니다.`;
  if (!confirm(msg)) return;
  await run(() => api.deleteProject(project.id));
}

function focusEdit(selector) {
  const input = document.querySelector(selector);
  if (input) { input.focus(); input.select?.(); }
}

function renderProjectOptions(select, selectedId) {
  select.replaceChildren(
    el("option", { value: "" }, "미분류"),
    ...state.projects.map((p) => el("option", { value: p.id }, p.name)),
  );
  select.value = selectedId ?? "";
}

function renderTodos() {
  const today = todayLocal();
  $("todo-list").replaceChildren(...state.todos.map((t) => todoItem(t, today)));
  $("empty").hidden = state.todos.length > 0;
  const done = state.todos.filter((t) => t.is_done).length;
  const overdue = state.todos.filter((t) => isOverdue(t, today)).length;
  $("list-summary").textContent =
    `전체 ${state.todos.length}건 · 완료 ${done}건` + (overdue ? ` · 마감 지남 ${overdue}건` : "");
}

function todoItem(todo, today) {
  const classes = ["todo"];
  if (todo.is_done) classes.push("done");
  if (isOverdue(todo, today)) classes.push("overdue");

  const checkbox = el("input", {
    type: "checkbox",
    checked: todo.is_done,
    "aria-label": `${todo.title} 완료 여부`,
    onchange: () => run(() => api.updateTodo(todo.id, { is_done: checkbox.checked })),
  });

  if (todo.id === state.editingTodo) {
    return el("li", { class: classes.join(" "), "data-id": todo.id }, checkbox, todoEditForm(todo));
  }

  return el(
    "li",
    { class: classes.join(" "), "data-id": todo.id },
    checkbox,
    el(
      "div",
      { class: "todo-body" },
      el("span", { class: "todo-title" }, todo.title),
      el(
        "span",
        { class: "todo-meta" },
        todo.due_date && el("span", { class: "badge due" }, dueLabel(todo.due_date, today)),
        todo.is_done && el("span", { class: "badge" }, "완료"),
      ),
    ),
    el(
      "span",
      { class: "todo-actions" },
      el("button", { class: "link", type: "button", "aria-label": `${todo.title} 수정`,
        onclick: () => { state.editingTodo = todo.id; render(); focusEdit(".todo-edit .edit-title"); } }, "수정"),
      el("button", { class: "link danger", type: "button", "aria-label": `${todo.title} 삭제`,
        onclick: () => removeTodo(todo) }, "삭제"),
    ),
  );
}

function todoEditForm(todo) {
  const title = el("input", { class: "edit-title", type: "text", value: todo.title, maxLength: 200, "aria-label": "할 일 제목" });
  const due = el("input", { type: "date", value: todo.due_date ?? "", "aria-label": "마감일" });
  const project = el("select", { "aria-label": "소속 프로젝트" });
  renderProjectOptions(project, todo.project_id);
  const cancel = () => { state.editingTodo = null; render(); };

  const form = el(
    "form",
    {
      class: "todo-edit",
      onsubmit: async (e) => {
        e.preventDefault();
        const newTitle = title.value.trim();
        if (!newTitle) return showError("할 일 제목을 입력하세요.");
        const changes = {
          title: newTitle,
          due_date: due.value || null, // 비우면 마감일 제거
          project_id: project.value || null, // 미분류 선택 시 null
        };
        if (await run(() => api.updateTodo(todo.id, changes))) {
          state.editingTodo = null;
          render();
        }
      },
    },
    title,
    due,
    project,
    el("button", { type: "submit" }, "저장"),
    el("button", { type: "button", onclick: cancel }, "취소"),
  );
  form.addEventListener("keydown", (e) => { if (e.key === "Escape") cancel(); });
  return form;
}

async function removeTodo(todo) {
  if (!confirm(`'${todo.title}' 할 일을 삭제할까요?`)) return;
  await run(() => api.deleteTodo(todo.id));
}

// ---------- 동작 ----------
async function selectProject(id) {
  state.selected = id;
  state.editingTodo = null;
  savePrefs();
  try {
    await loadTodos();
    render();
  } catch (err) {
    showError(err);
  }
}

$("project-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("project-name");
  const name = input.value.trim();
  if (!name) return showError("프로젝트 이름을 입력하세요.");
  let created;
  const ok = await run(async () => { created = await api.createProject(name); });
  if (ok) {
    input.value = "";
    await selectProject(created.id); // 새로 만든 프로젝트로 이동
  }
});

$("todo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = $("todo-title").value.trim();
  if (!title) return showError("할 일 제목을 입력하세요.");
  const projectId = $("todo-project").value || null;
  const ok = await run(() =>
    api.createTodo({ title, project_id: projectId, due_date: $("todo-due").value || null }),
  );
  if (ok) {
    $("todo-title").value = "";
    $("todo-due").value = "";
    $("todo-title").focus();
  }
});

$("sort-select").addEventListener("change", async (e) => {
  state.sort = e.target.value;
  savePrefs();
  try {
    await loadTodos();
    render();
  } catch (err) {
    showError(err);
  }
});

// ---------- 로그인 (supabase 모드에서만) ----------
function resetState() {
  Object.assign(state, {
    projects: [],
    unassigned: { total_count: 0, done_count: 0 },
    selected: UNASSIGNED,
    todos: [],
    editingTodo: null,
    editingProject: null,
  });
}

function showLogin(message = "") {
  resetState(); // 이전 사용자의 데이터가 화면에 남지 않게 비운다
  $("app-view").hidden = true;
  $("current").hidden = true;
  $("user-box").hidden = true;
  $("login-view").hidden = false;
  $("login-message").textContent = message;
  $("login-password").value = "";
  $("login-email").focus();
}

async function showApp(user) {
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  $("current").hidden = false;
  $("user-box").hidden = !user; // sqlite 모드는 사용자 표시 없음
  $("user-email").textContent = user?.email ?? "";
  loadPrefs();
  $("sort-select").value = state.sort;
  await refresh();
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("login-button");
  button.disabled = true;
  $("login-message").textContent = "";
  try {
    // 비밀번호는 백엔드로만 전송되고, 백엔드가 Supabase 에 확인한 뒤 HttpOnly 쿠키를 심는다.
    const { user } = await api.login($("login-email").value.trim(), $("login-password").value);
    $("login-password").value = "";
    await showApp(user);
  } catch (err) {
    $("login-message").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});

$("logout-button").addEventListener("click", async () => {
  try {
    await api.logout();
  } catch (err) {
    showError(err);
  }
  try { localStorage.removeItem(PREFS_KEY); } catch { /* 무시 */ }
  showLogin("로그아웃되었습니다.");
});

// 갱신까지 실패한 경우 (api.js 가 알림)
window.addEventListener(AUTH_REQUIRED_EVENT, () => showLogin("로그인이 만료되었습니다. 다시 로그인하세요."));

// ---------- 시작 ----------
async function boot() {
  const { auth_required: authRequired, user } = await api.me();
  if (authRequired && !user) {
    showLogin();
  } else {
    await showApp(user);
  }
}

boot().catch(showError);
