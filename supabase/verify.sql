-- schema.sql 실행 후 확인용 조회 (읽기만 하며 데이터를 바꾸지 않는다)
-- SQL Editor 에서 블록을 하나씩 선택해 실행하면 결과를 따로 볼 수 있다.

-- [1] RLS 가 켜져 있는가? (relrowsecurity = true 여야 한다)
select relname as table_name, relrowsecurity as rls_enabled
from pg_class
where oid in ('public.projects'::regclass, 'public.todos'::regclass);

-- [2] 어떤 정책이 있는가? (테이블마다 SELECT/INSERT/UPDATE/DELETE 4개)
--     qual = USING 조건, with_check = WITH CHECK 조건
select tablename, policyname, cmd, roles, qual, with_check
from pg_policies
where schemaname = 'public'
order by tablename, cmd;

-- [3] 역할별 테이블 권한(GRANT) — anon 은 하나도 없어야 한다
select grantee, table_name, string_agg(privilege_type, ', ' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema = 'public'
  and table_name in ('projects', 'todos')
  and grantee in ('anon', 'authenticated')
group by grantee, table_name
order by grantee, table_name;

-- [4] 제약조건 — 복합 외래키와 ON DELETE SET NULL (project_id) 확인
select conrelid::regclass as table_name, conname, pg_get_constraintdef(oid) as definition
from pg_constraint
where conrelid in ('public.projects'::regclass, 'public.todos'::regclass)
order by table_name, conname;
