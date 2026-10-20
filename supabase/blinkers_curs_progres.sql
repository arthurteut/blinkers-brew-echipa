-- Progresul cursului de manager Blinkers Brew (echipa.blinkersbrew.ro).
-- Aplicat în proiectul Supabase „atc-toolkit”. Tabelul nu e accesibil direct:
-- RLS activ, fără politici. Se citește și se scrie doar prin cele două funcții,
-- care cer cheia derivată din parola de manager:
--   cheie = sha256_hex("bb-curs:" + parola de manager)   (calculată în browser)
--   cheie_hash = sha256_hex(cheie)                        (păstrată în tabel)
create table public.blinkers_curs_progres (
  id text primary key,
  cheie_hash text not null unique,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.blinkers_curs_progres enable row level security;
revoke all on public.blinkers_curs_progres from anon, authenticated;

create function public.blinkers_curs_citeste(p_cheie text)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object('data', p.data, 'updated_at', p.updated_at)
  from public.blinkers_curs_progres p
  where p.cheie_hash = encode(sha256(convert_to(p_cheie, 'UTF8')), 'hex');
$$;

create function public.blinkers_curs_salveaza(p_cheie text, p_data jsonb)
returns timestamptz
language plpgsql
security definer
set search_path = ''
as $$
declare
  t timestamptz;
begin
  if octet_length(p_data::text) > 262144 then
    raise exception 'Progres prea mare';
  end if;
  update public.blinkers_curs_progres
     set data = p_data, updated_at = now()
   where cheie_hash = encode(sha256(convert_to(p_cheie, 'UTF8')), 'hex')
  returning updated_at into t;
  if t is null then
    raise exception 'Cheie necunoscută' using errcode = '28000';
  end if;
  return t;
end;
$$;

revoke all on function public.blinkers_curs_citeste(text) from public;
revoke all on function public.blinkers_curs_salveaza(text, jsonb) from public;
grant execute on function public.blinkers_curs_citeste(text) to anon, authenticated;
grant execute on function public.blinkers_curs_salveaza(text, jsonb) to anon, authenticated;

-- Rândul cursului (o singură dată). La schimbarea parolei de manager, se
-- actualizează cheie_hash cu valoarea nouă (progresul rămâne):
--   printf '%s' "bb-curs:PAROLA" | sha256sum   → cheie
--   printf '%s' "CHEIE"          | sha256sum   → cheie_hash
-- insert into public.blinkers_curs_progres (id, cheie_hash) values ('curs-manager', '<cheie_hash>');
-- update public.blinkers_curs_progres set cheie_hash = '<cheie_hash nou>' where id = 'curs-manager';
