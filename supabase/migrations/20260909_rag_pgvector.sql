-- FOLIO RAG: books + passages with pgvector embeddings
-- Run in Supabase SQL Editor or via supabase db push

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Books indexed for RAG chat
-- ---------------------------------------------------------------------------
create table if not exists public.rag_books (
  id text primary key,                    -- mobile book id (AsyncStorage)
  title text not null,
  passage_count integer not null default 0,
  status text not null default 'indexing'
    check (status in ('indexing', 'ready', 'failed')),
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Text chunks + embeddings (Gemini text-embedding-004 = 768 dimensions)
-- ---------------------------------------------------------------------------
create table if not exists public.rag_passages (
  id uuid primary key default gen_random_uuid(),
  book_id text not null references public.rag_books (id) on delete cascade,
  chapter_id integer not null,
  chapter_numeral text,
  chapter_title text,
  chunk_index integer not null,
  text text not null,
  start_char integer,
  embedding vector(768) not null,
  created_at timestamptz not null default now(),
  unique (book_id, chapter_id, chunk_index)
);

create index if not exists rag_passages_book_id_idx
  on public.rag_passages (book_id);

-- HNSW index for cosine similarity (create after first rows exist, or leave for later)
-- Supabase pgvector supports HNSW on paid; on free tier this still works for moderate size.
create index if not exists rag_passages_embedding_hnsw_idx
  on public.rag_passages
  using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Similarity search RPC (called from backend with service role key)
-- ---------------------------------------------------------------------------
create or replace function public.match_rag_passages(
  query_embedding vector(768),
  match_book_id text,
  match_count integer default 8
)
returns table (
  id uuid,
  chapter_id integer,
  chapter_numeral text,
  chapter_title text,
  chunk_index integer,
  text text,
  start_char integer,
  similarity double precision
)
language sql
stable
as $$
  select
    p.id,
    p.chapter_id,
    p.chapter_numeral,
    p.chapter_title,
    p.chunk_index,
    p.text,
    p.start_char,
    1 - (p.embedding <=> query_embedding) as similarity
  from public.rag_passages p
  where p.book_id = match_book_id
  order by p.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_rag_books_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists rag_books_updated_at on public.rag_books;
create trigger rag_books_updated_at
  before update on public.rag_books
  for each row
  execute function public.set_rag_books_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: backend uses service_role key (bypasses RLS).
-- Enable RLS in Phase 5 when adding user_id + client access.
-- ---------------------------------------------------------------------------
alter table public.rag_books enable row level security;
alter table public.rag_passages enable row level security;

-- No public policies yet — only service_role from backend can read/write.
