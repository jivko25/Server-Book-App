-- Run if tables were created without all columns from the main migration

alter table public.rag_books
  add column if not exists error_message text,
  add column if not exists updated_at timestamptz not null default now();

alter table public.rag_passages
  add column if not exists chunk_index integer;

-- Backfill chunk_index for existing rows (safe if column was just added)
update public.rag_passages
set chunk_index = 0
where chunk_index is null;

alter table public.rag_passages
  alter column chunk_index set not null;

create unique index if not exists rag_passages_book_chapter_chunk_idx
  on public.rag_passages (book_id, chapter_id, chunk_index);
