-- Chalk chat schema. Idempotent: safe to re-run.
-- Chat data lives in SQLite (data/chalk.db) by Chalk's locked decision;
-- Lantern's deck store stays filesystem. Both ride the same zip backup.

create table if not exists projects (
  id           text primary key,
  name         text not null,
  instructions text not null default '',   -- the system prompt
  context      text not null default '',   -- pasted "project knowledge"
  created_at   text not null,
  updated_at   text not null,
  deleted_at   text
);

create table if not exists conversations (
  id          text primary key,
  project_id  text not null references projects(id) on delete cascade,
  title       text not null default 'New conversation',
  model       text not null default 'claude-haiku-4-5',
  created_at  text not null,
  updated_at  text not null,
  deleted_at  text
);

create table if not exists messages (
  id              text primary key,
  conversation_id text not null references conversations(id) on delete cascade,
  role            text not null check (role in ('user','assistant')),
  content         text not null,
  created_at      text not null
);

create index if not exists idx_conversations_project
  on conversations(project_id);
create index if not exists idx_messages_conversation
  on messages(conversation_id);
