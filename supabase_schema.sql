-- Campus Device Security System schema for Supabase
-- Run this in Supabase SQL Editor.

-- Ensure UUID generation is available
create extension if not exists pgcrypto;

create table if not exists public.student_devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  full_name text not null,
  department text not null,
  student_id text not null unique,
  laptop_brand text not null,
  serial_number text not null unique,
  profile_image_path text,
  is_stolen boolean not null default false,
  pass_issued_at timestamptz,
  pass_expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_student_devices_serial_number
  on public.student_devices(serial_number);

create index if not exists idx_student_devices_user_id
  on public.student_devices(user_id);

create table if not exists public.security_config (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

insert into public.security_config(key, value)
values ('daily_secret_color', 'BLUE')
on conflict (key) do nothing;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_student_devices_updated_at on public.student_devices;
create trigger trg_student_devices_updated_at
before update on public.student_devices
for each row execute function public.set_updated_at();

drop trigger if exists trg_security_config_updated_at on public.security_config;
create trigger trg_security_config_updated_at
before update on public.security_config
for each row execute function public.set_updated_at();

-- Row Level Security
alter table public.student_devices enable row level security;
alter table public.security_config enable row level security;

-- Students can read/write only their own device record
drop policy if exists "students_select_own_device" on public.student_devices;
create policy "students_select_own_device"
on public.student_devices
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "students_insert_own_device" on public.student_devices;
create policy "students_insert_own_device"
on public.student_devices
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "students_update_own_device" on public.student_devices;
create policy "students_update_own_device"
on public.student_devices
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- Anyone authenticated can read secret color for guard verification
drop policy if exists "authenticated_read_security_config" on public.security_config;
create policy "authenticated_read_security_config"
on public.security_config
for select
to authenticated
using (true);

-- Optional: only service role should update security_config (no update policy for authenticated users)

-- Storage bucket for profile images
insert into storage.buckets (id, name, public)
values ('student-photos', 'student-photos', true)
on conflict (id) do nothing;

-- Allow authenticated users to upload/read their own photos
drop policy if exists "student_photos_select" on storage.objects;
create policy "student_photos_select"
on storage.objects
for select
to authenticated
using (bucket_id = 'student-photos');

drop policy if exists "student_photos_insert_own_folder" on storage.objects;
create policy "student_photos_insert_own_folder"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'student-photos'
  and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists "student_photos_update_own_folder" on storage.objects;
create policy "student_photos_update_own_folder"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'student-photos'
  and (storage.foldername(name))[1] = auth.uid()::text
)
with check (
  bucket_id = 'student-photos'
  and (storage.foldername(name))[1] = auth.uid()::text
);
