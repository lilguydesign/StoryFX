-- Owner-scoped Android recovery. The private table holds references, never PINs.
BEGIN;
CREATE SCHEMA IF NOT EXISTS storyfx_security;
REVOKE ALL ON SCHEMA storyfx_security FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS storyfx_security.pin_backups (
  owner_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  profile text NOT NULL CHECK (length(profile) BETWEEN 1 AND 100),
  secret_id uuid NOT NULL UNIQUE REFERENCES vault.secrets(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (owner_id, profile)
);
ALTER TABLE storyfx_security.pin_backups ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON storyfx_security.pin_backups FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.storyfx_pin_backup_v1(
  p_operation text, p_profile text, p_pin text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
SET statement_timeout = '8s' SET lock_timeout = '2s'
AS $function$
DECLARE
  subject uuid := auth.uid();
  saved storyfx_security.pin_backups%ROWTYPE;
  secret_uuid uuid;
  clear_value text;
BEGIN
  IF subject IS NULL OR public.storyfx_owner_allowed_v1() IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'OWNER_ACCESS_REQUIRED' USING ERRCODE = '42501';
  END IF;
  IF p_operation IS NULL OR p_operation NOT IN ('save','status','restore','remove')
     OR p_profile IS NULL OR length(p_profile) NOT BETWEEN 1 AND 100
     OR btrim(p_profile) <> p_profile THEN
    RAISE EXCEPTION 'BACKUP_REQUEST_INVALID' USING ERRCODE = '22023';
  END IF;
  IF p_operation = 'save' AND (p_pin IS NULL OR p_pin !~ '^[0-9]{4,16}$') THEN
    RAISE EXCEPTION 'BACKUP_REQUEST_INVALID' USING ERRCODE = '22023';
  END IF;
  IF p_operation <> 'save' AND p_pin IS NOT NULL THEN
    RAISE EXCEPTION 'BACKUP_REQUEST_INVALID' USING ERRCODE = '22023';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(subject::text || ':' || p_profile, 0));
  SELECT * INTO saved FROM storyfx_security.pin_backups
    WHERE owner_id = subject AND profile = p_profile FOR UPDATE;
  IF p_operation = 'save' THEN
    IF saved.secret_id IS NULL THEN
      secret_uuid := vault.create_secret(p_pin,
        'storyfx-pin:' || subject::text || ':' || pg_catalog.md5(p_profile),
        'StoryFX Android recovery PIN');
      INSERT INTO storyfx_security.pin_backups(owner_id,profile,secret_id)
        VALUES(subject,p_profile,secret_uuid) RETURNING * INTO saved;
    ELSE
      PERFORM vault.update_secret(saved.secret_id,p_pin);
      UPDATE storyfx_security.pin_backups SET updated_at = now()
        WHERE owner_id = subject AND profile = p_profile RETURNING * INTO saved;
    END IF;
  ELSIF p_operation = 'restore' AND saved.secret_id IS NOT NULL THEN
    SELECT decrypted_secret INTO clear_value FROM vault.decrypted_secrets
      WHERE id = saved.secret_id;
    IF clear_value IS NULL OR clear_value !~ '^[0-9]{4,16}$' THEN
      RAISE EXCEPTION 'BACKUP_UNAVAILABLE' USING ERRCODE = '22023';
    END IF;
    RETURN jsonb_build_object('available',true,'pin',clear_value);
  ELSIF p_operation = 'remove' AND saved.secret_id IS NOT NULL THEN
    DELETE FROM storyfx_security.pin_backups WHERE owner_id=subject AND profile=p_profile;
    DELETE FROM vault.secrets WHERE id=saved.secret_id;
    RETURN jsonb_build_object('available',false);
  END IF;
  RETURN jsonb_build_object('available',saved.secret_id IS NOT NULL,
    'updated_at',saved.updated_at);
END;
$function$;
REVOKE ALL ON FUNCTION public.storyfx_pin_backup_v1(text,text,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.storyfx_pin_backup_v1(text,text,text) TO authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;
