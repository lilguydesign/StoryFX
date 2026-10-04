import json
import tempfile
import unittest
from pathlib import Path

from storyfx_server.legacy_preview import preview_legacy_plan


class LegacyPreviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.profiles = {"phone": {"enabled": True, "offset_minutes": 15, "label": "Validation technique",
                                   "device_id": "PRIVATE_NETWORK", "adb_serial": "PRIVATE_SERIAL",
                                   "pin": "PRIVATE_PIN", "gallery": {"path": "PRIVATE_PATH"}},
                         "disabled": {"enabled": False}}
        self.systems = {"daily": ["23:55", "07:00"]}
        self.rows = [{"device": "phone", "system": "daily", "engine": "intro+multi",
                      "album": "PRIVATE_INTRO", "album2": "PRIVATE_ALBUM", "count": 2,
                      "platform": "WhatsApp", "page_name": "PRIVATE_PAGE"}]
        self.albums = [{"name": "PRIVATE_ALBUM", "count_per_post": 11}, {"name": "PRIVATE_INTRO"}]

    def preview(self, day="2026-10-04", zone="Africa/Douala"):
        for filename, member, content in (
            ("profiles.json", "profiles", self.profiles), ("systems.json", "systems", self.systems),
            ("matrix.json", "rows", self.rows), ("albums.json", "albums", self.albums)):
            (self.folder / filename).write_text(json.dumps({member: content}), encoding="utf-8")
        return preview_legacy_plan(self.folder, reference_date=day, timezone_name=zone)

    def warning_codes(self, result):
        return {warning["code"] for warning in result["warnings"]}

    def test_inert_transport_free_preview_preserves_album_count_and_offset(self):
        result = self.preview()
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["activation_allowed"])
        self.assertEqual(result["plans_created"], 0)
        self.assertEqual(result["stats"]["disabled_devices"], 1)
        self.assertEqual(result["stats"]["preview_jobs"], 2)
        job = next(item for item in result["jobs"] if item["base_time"] == "23:55")
        self.assertEqual(job["count"], 11)
        self.assertEqual(job["effective_local_time"], "00:10")
        self.assertEqual(job["due_at"], "2026-10-03T23:10:00Z")
        self.assertIn("physical_device_identity_unverified", self.warning_codes(result))
        encoded = json.dumps(result)
        for private_value in ("PRIVATE_NETWORK", "PRIVATE_SERIAL", "PRIVATE_PIN", "PRIVATE_PATH",
                              "PRIVATE_INTRO", "PRIVATE_ALBUM", "PRIVATE_PAGE"):
            self.assertNotIn(private_value, encoded)

    def test_negative_offset_wraps_without_changing_legacy_daily_semantics(self):
        self.profiles["phone"]["offset_minutes"] = -15
        self.systems["daily"] = {"times": ["00:05"]}
        result = self.preview()
        self.assertEqual(result["jobs"][0]["effective_local_time"], "23:50")
        self.assertEqual(result["jobs"][0]["due_at"], "2026-10-04T22:50:00Z")

    def test_ids_are_deterministic_unique_across_rows_platforms_engines_and_dates(self):
        self.rows.append(dict(self.rows[0], platform="Instagram", engine="multi"))
        self.rows.append(dict(self.rows[0]))
        first, repeated = self.preview(), self.preview()
        keys = [job["preview_job_id"] for job in first["jobs"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys, [job["preview_job_id"] for job in repeated["jobs"]])
        next_day = self.preview("2026-10-05")
        self.assertTrue(set(keys).isdisjoint(job["preview_job_id"] for job in next_day["jobs"]))

    def test_disabled_orphan_and_malformed_rows_are_excluded(self):
        self.rows.extend([dict(self.rows[0], device="disabled"), dict(self.rows[0], device="absent"),
                          dict(self.rows[0], system="absent"), dict(self.rows[0], engine="script"),
                          dict(self.rows[0], engine=[]), dict(self.rows[0], platform={}), None])
        result = self.preview()
        self.assertEqual(result["stats"]["preview_jobs"], 2)
        self.assertTrue({"orphan_device_row", "orphan_system_row", "unsupported_engine_or_platform",
                         "invalid_matrix_row"}.issubset(self.warning_codes(result)))

    def test_duplicate_times_are_deduplicated_invalid_times_are_reported(self):
        self.systems["daily"] = ["07:00", "07:00", "25:00", "7:00", "07:0x", None]
        result = self.preview()
        self.assertEqual(result["stats"]["preview_jobs"], 1)
        self.assertIn("duplicate_system_time", self.warning_codes(result))
        self.assertIn("invalid_or_ambiguous_schedule_time", self.warning_codes(result))

    def test_invalid_profile_boolean_and_offset_never_activate(self):
        self.profiles["phone"]["enabled"] = "true"
        self.assertEqual(self.preview()["stats"]["preview_jobs"], 0)
        self.profiles["phone"]["enabled"] = True
        self.profiles["phone"]["offset_minutes"] = "shell command"
        result = self.preview()
        self.assertEqual(result["stats"]["preview_jobs"], 0)
        self.assertIn("invalid_profile_offset", self.warning_codes(result))

    def test_intro_count_ignores_multi_album_override(self):
        self.rows[0]["engine"] = "intro"
        self.albums[1]["count_per_post"] = 19
        self.assertEqual(self.preview()["jobs"][0]["count"], 1)

    def test_missing_metadata_remains_warning_but_invalid_count_is_excluded(self):
        self.albums = []
        result = self.preview()
        self.assertIn("unregistered_album", self.warning_codes(result))
        self.assertEqual(result["jobs"][0]["count"], 2)
        self.rows[0]["count"] = -1
        self.assertEqual(self.preview()["stats"]["preview_jobs"], 0)

    def test_daylight_saving_gaps_and_ambiguities_are_not_silently_guessed(self):
        self.profiles["phone"]["offset_minutes"] = 0
        self.systems["daily"] = ["02:30"]
        for day in ("2026-03-29", "2026-10-25"):
            with self.subTest(day=day):
                result = self.preview(day, "Europe/Paris")
                self.assertEqual(result["stats"]["preview_jobs"], 0)
                self.assertIn("invalid_or_ambiguous_schedule_time", self.warning_codes(result))

    def test_config_structure_and_invalid_calendar_raise_safe_errors(self):
        self.preview()
        (self.folder / "profiles.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "profiles.json"):
            preview_legacy_plan(self.folder)
        self.preview()
        with self.assertRaisesRegex(ValueError, "date or timezone"):
            preview_legacy_plan(self.folder, reference_date="2026-02-31")
        with self.assertRaisesRegex(ValueError, "date or timezone"):
            preview_legacy_plan(self.folder, timezone_name="Invalid/Zone")


if __name__ == "__main__":
    unittest.main()
