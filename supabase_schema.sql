-- Campus Device Security System schema for Supabase
-- Run this in Supabase SQL Editor.
-- Replace admin@campus.edu below with your real admin login email.

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

create table if not exists public.exit_logs (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references auth.users(id) on delete cascade,
  student_name text not null,
  laptop_serial text not null,
  ip_address text,
  timestamp timestamptz not null default now()
);

create index if not exists idx_student_devices_serial_number
  on public.student_devices(serial_number);

create index if not exists idx_student_devices_user_id
  on public.student_devices(user_id);

create index if not exists idx_exit_logs_student_id
  on public.exit_logs(student_id);

create index if not exists idx_exit_logs_laptop_serial
  on public.exit_logs(laptop_serial);

create index if not exists idx_exit_logs_timestamp
  on public.exit_logs(timestamp desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.enforce_student_update_scope()
returns trigger
language plpgsql
as $$
declare
  is_admin boolean := lower(coalesce(auth.jwt() ->> 'email', '')) = 'admin@campus.edu';
begin
  -- Admin can update any field.
  if is_admin then
    return new;
  end if;

  -- Non-admin authenticated users can only update their own pass/stolen state.
  if auth.uid() is null or auth.uid() <> old.user_id then
    raise exception 'Not allowed to update this device record';
  end if;

  if new.user_id is distinct from old.user_id
     or new.full_name is distinct from old.full_name
     or new.department is distinct from old.department
     or new.student_id is distinct from old.student_id
     or new.laptop_brand is distinct from old.laptop_brand
     or new.serial_number is distinct from old.serial_number
     or new.profile_image_path is distinct from old.profile_image_path
     or new.created_at is distinct from old.created_at
     or new.id is distinct from old.id then
    raise exception 'Students can only update pass status or stolen status';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_student_devices_updated_at on public.student_devices;
create trigger trg_student_devices_updated_at
before update on public.student_devices
for each row execute function public.set_updated_at();

drop trigger if exists trg_student_devices_update_scope on public.student_devices;
create trigger trg_student_devices_update_scope
before update on public.student_devices
for each row execute function public.enforce_student_update_scope();

-- Row Level Security
alter table public.student_devices enable row level security;
alter table public.exit_logs enable row level security;

-- Students can only read their own records
drop policy if exists "students_select_own_device" on public.student_devices;
create policy "students_select_own_device"
on public.student_devices
for select
to authenticated
using (auth.uid() = user_id);

-- Admin-only registration (insert)
drop policy if exists "admin_insert_devices" on public.student_devices;
create policy "admin_insert_devices"
on public.student_devices
for insert
to authenticated
with check (lower(auth.jwt() ->> 'email') = 'admin@campus.edu');

-- Admin can update any device profile fields
drop policy if exists "admin_update_devices" on public.student_devices;
create policy "admin_update_devices"
on public.student_devices
for update
to authenticated
using (lower(auth.jwt() ->> 'email') = 'admin@campus.edu')
with check (lower(auth.jwt() ->> 'email') = 'admin@campus.edu');

-- Students can update only their own pass/stolen status.
-- Profile fields are also protected by enforce_student_update_scope trigger.
drop policy if exists "students_update_pass_or_stolen" on public.student_devices;
create policy "students_update_pass_or_stolen"
on public.student_devices
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- Exit log visibility (admin only when using authenticated client)
drop policy if exists "admin_select_exit_logs" on public.exit_logs;
create policy "admin_select_exit_logs"
on public.exit_logs
for select
to authenticated
using (lower(auth.jwt() ->> 'email') = 'admin@campus.edu');

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
