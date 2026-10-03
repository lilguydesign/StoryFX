BEGIN;
CREATE TABLE IF NOT EXISTS public.storyfx_android_releases (
  version text PRIMARY KEY CHECK (version ~ '^\d+\.\d+\.\d+$'),
  channel text NOT NULL DEFAULT 'stable' CHECK (channel = 'stable'),
  version_code integer NOT NULL UNIQUE CHECK (version_code > 0),
  download_url text NOT NULL UNIQUE,
  sha256 text NOT NULL CHECK (sha256 ~ '^[A-Fa-f0-9]{64}$'),
  byte_size bigint NOT NULL CHECK (byte_size > 0),
  released_at timestamptz NOT NULL DEFAULT now(),
  CHECK (download_url = 'https://api.formafx.com/downloads/storyfx-android/StoryFX-Android-'
         || version || '-v' || version_code::text || '.apk')
);
ALTER TABLE public.storyfx_android_releases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.storyfx_android_releases FROM anon, authenticated;
GRANT SELECT ON public.storyfx_android_releases TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
