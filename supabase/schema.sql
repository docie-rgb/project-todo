-- =====================================================================
-- Project Todo: Supabase(PostgreSQL) 스키마 + 권한 + RLS
--
-- 실행 위치 : Supabase 대시보드 → SQL Editor → New query → 전체 붙여 넣기 → Run
-- 실행 횟수 : 새 프로젝트에서 한 번. 다시 실행하면 "already exists" 오류가 나고
--            begin/commit 으로 묶여 있어 아무것도 바뀌지 않는다.
-- 근거 문서 : DB_DESIGN.md §5 (테이블·제약·정책은 동일, §5-3-1 권한 부분이 추가됨)
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- 1. 테이블
-- ---------------------------------------------------------------------

create table public.projects (
  id         uuid primary key default gen_random_uuid(),
  -- 행의 주인. 값을 보내지 않으면 "지금 요청한 로그인 사용자"가 자동으로 들어간다.
  user_id    uuid not null default auth.uid()
             references auth.users (id) on delete cascade,
  -- 앞뒤 공백 없는 값만, 빈 문자열 금지 (공백 제거는 앱이 저장 전에 수행)
  name       text not null check (name = btrim(name) and name <> ''),
  created_at timestamptz not null default now(),
  -- 아래 todos 의 복합 외래키가 가리킬 대상 (id 하나만으로도 유일하지만, 쌍으로 참조하기 위해 필요)
  constraint projects_id_user_id_key unique (id, user_id)
);

-- 같은 사용자 안에서만 이름 중복 금지, 영문 대소문자 무시 (다른 사용자끼리는 같은 이름 허용)
create unique index projects_user_name_ci_key
  on public.projects (user_id, lower(name));

create table public.todos (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid()
             references auth.users (id) on delete cascade,
  project_id uuid,                     -- NULL = 미분류
  title      text not null check (length(btrim(title)) > 0),
  is_done    boolean not null default false,
  due_date   date,                     -- NULL = 마감일 없음
  created_at timestamptz not null default now(),

  -- (project_id, user_id) 쌍이 projects 에 있어야 한다
  --   → 할 일의 주인과 프로젝트의 주인이 같아야만 연결된다.
  -- project_id 가 NULL(미분류)이면 이 검사는 건너뛴다.
  -- 프로젝트가 삭제되면 project_id 만 NULL 로 바꾸고 user_id 는 그대로 둔다.
  constraint todos_project_owner_fkey
    foreign key (project_id, user_id)
    references public.projects (id, user_id)
    on delete set null (project_id)
);

create index todos_user_project_idx on public.todos (user_id, project_id);

-- ---------------------------------------------------------------------
-- 2. 권한 (GRANT) — "이 역할이 이 테이블에 이런 종류의 작업을 할 수 있는가"
--    anon          = 로그인하지 않은 요청 (publishable 키만 있음)
--    authenticated = 로그인한 사용자의 토큰이 있는 요청
-- ---------------------------------------------------------------------

-- Supabase 가 새 테이블에 자동으로 주는 권한을 일단 모두 회수한다.
revoke all on table public.projects, public.todos from anon, authenticated;

-- 로그인한 사용자에게만 4가지 작업을 허용한다.
-- (어느 "행"에 할 수 있는지는 아래 RLS 정책이 정한다)
grant select, insert, update, delete on table public.projects, public.todos to authenticated;

-- ---------------------------------------------------------------------
-- 3. RLS (Row Level Security) — "어느 행에 대해 그 작업을 할 수 있는가"
-- ---------------------------------------------------------------------

alter table public.projects enable row level security;
alter table public.todos    enable row level security;

-- USING      : 이미 있는 행 중 "보이고 손댈 수 있는" 행의 조건 (SELECT·UPDATE·DELETE)
-- WITH CHECK : 새로 쓰려는 행이 "저장되어도 되는" 조건       (INSERT·UPDATE)
-- (select auth.uid()) 는 요청의 로그인 사용자 ID. select 로 감싸면 행마다 다시 계산하지 않는다.

-- projects
create policy projects_select on public.projects
  for select to authenticated
  using (user_id = (select auth.uid()));

create policy projects_insert on public.projects
  for insert to authenticated
  with check (user_id = (select auth.uid()));

create policy projects_update on public.projects
  for update to authenticated
  using      (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy projects_delete on public.projects
  for delete to authenticated
  using (user_id = (select auth.uid()));

-- todos (미분류 할 일도 user_id 로 똑같이 보호된다)
create policy todos_select on public.todos
  for select to authenticated
  using (user_id = (select auth.uid()));

create policy todos_insert on public.todos
  for insert to authenticated
  with check (user_id = (select auth.uid()));

create policy todos_update on public.todos
  for update to authenticated
  using      (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy todos_delete on public.todos
  for delete to authenticated
  using (user_id = (select auth.uid()));

-- "다른 사용자의 프로젝트에 내 할 일 연결"은 정책이 아니라 위의 복합 외래키가 막는다.

commit;
