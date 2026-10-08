package com.formafx.storyfx.agent.publication

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationProfilesTest {
    private val primary = "Validation technique principale"
    private val secondary = "Validation technique supplémentaire"
    private fun entry(name: String = primary, id: String = "00000000-0000-0000-0000-000000000001",
                      platform: String = "WhatsApp", isPrimary: Boolean = true) = JSONObject()
        .put("profile_id", id).put("profile", name).put("platform", platform).put("primary", isPrimary)
        .put("enabled", true).put("ready", isPrimary).put("reason", if (isPrimary) "" else "ADAPTER_NOT_VALIDATED")

    private fun settings(): JSONObject = JSONObject()
        .put("binding", JSONObject().put("profile", primary).put("enabled", 1).put("reason", ""))
        .put("profiles", JSONArray().put(JSONObject().put("name", primary).put("enabled", true))
            .put(JSONObject().put("name", "Profil non associé").put("enabled", true)))
        .put("authorized_profiles", JSONArray().put(entry()).put(entry(secondary,
            "00000000-0000-0000-0000-000000000002", "Facebook", false)))
        .put("capabilities", JSONObject().put("facebook", JSONObject().put("ready", false).put("reason", "ADAPTER_NOT_VALIDATED")))

    private fun job(profile: String = primary, platform: String = "WhatsApp") = JSONObject()
        .put("id", "00000000-0000-0000-0000-000000000099").put("occurrence_id", "a".repeat(64))
        .put("payload", JSONObject().put("device", profile).put("platform", platform)
            .put("execution_origin", "web_android_agent").put("web_triggered", true).put("engine", "multi")
            .put("count", 3).put("due_at", "2020-01-01T00:00:00Z").put("album", "Validation technique"))

    @Test fun explicitAdditionalProfilesNeverChangeWhatsAppPrimary() {
        val profiles = PublicationProfiles.read(settings())
        assertTrue(profiles.explicitContract)
        assertEquals(2, profiles.authorized.size)
        assertEquals(primary, profiles.requirePrimary(primary).profile)
        assertEquals(3, PublicationProviders.validate(job(), profiles, primary).getInt("count"))
        assertThrows(IllegalArgumentException::class.java) {
            PublicationProviders.validate(job(secondary), profiles, primary)
        }
    }

    @Test fun catalogPresenceCannotGrantPermission() {
        val profiles = PublicationProfiles.read(settings())
        assertThrows(IllegalArgumentException::class.java) {
            PublicationProviders.validate(job("Profil non associé"), profiles, primary)
        }
        assertThrows(IllegalArgumentException::class.java) { profiles.requirePrimary(secondary) }
    }

    @Test fun facebookStaysUnimplementedEvenWithAllServerFlagsForgedReady() {
        val data = settings()
        data.getJSONArray("authorized_profiles").getJSONObject(1).put("ready", true).put("reason", "")
        data.getJSONObject("capabilities").getJSONObject("facebook").put("ready", true).put("reason", "")
        val profiles = PublicationProfiles.read(data)
        val error = assertThrows(IllegalArgumentException::class.java) {
            PublicationProviders.validate(job(secondary, "Facebook"), profiles, primary)
        }
        assertEquals("ADAPTER_NOT_VALIDATED", error.message)
        assertTrue(PublicationProviders.description(profiles.authorized[1]).contains("indisponible"))
    }

    @Test fun oldServerKeepsOnlyExactPrimaryWithoutInferringCatalogSiblings() {
        val data = settings().apply { remove("authorized_profiles"); remove("capabilities") }
        val profiles = PublicationProfiles.read(data)
        assertFalse(profiles.explicitContract)
        assertEquals(listOf(primary), profiles.authorized.map { it.profile })
        assertEquals(3, PublicationProviders.validate(job(), profiles, primary).getInt("count"))
        assertThrows(IllegalArgumentException::class.java) {
            PublicationProviders.validate(job(secondary, "Facebook"), profiles, primary)
        }
    }

    @Test fun explicitEmptyOrInvalidContractNeverFallsBackToLegacyGrant() {
        for (value in listOf(JSONArray(), JSONObject.NULL, "not a list")) {
            val data = settings().put("authorized_profiles", value)
            assertThrows(Exception::class.java) { PublicationProfiles.read(data) }
        }
        val data = settings().put("binding", JSONObject.NULL).put("authorized_profiles", JSONArray())
        assertTrue(PublicationProfiles.read(data).authorized.isEmpty())
        assertThrows(IllegalArgumentException::class.java) { PublicationProfiles.read(data).requirePrimary(primary) }
    }

    @Test fun duplicateNamesIdsAndPrimaryMismatchAreRejected() {
        for ((key, value) in listOf("profile" to primary,
            "profile_id" to "00000000-0000-0000-0000-000000000001", "primary" to true, "platform" to "WhatsApp")) {
            val data = settings()
            data.getJSONArray("authorized_profiles").getJSONObject(1).put(key, value)
            assertThrows(IllegalArgumentException::class.java) { PublicationProfiles.read(data) }
        }
        val data = settings()
        data.getJSONObject("binding").put("profile", "Autre profil")
        assertThrows(IllegalArgumentException::class.java) { PublicationProfiles.read(data) }
    }

    @Test fun malformedBooleansUnknownProviderAndMissingIdsCannotBroadenScope() {
        for ((key, value) in listOf("enabled" to "true", "ready" to 1, "primary" to "true",
            "platform" to "Unknown", "profile_id" to "1", "profile" to 123)) {
            val data = settings()
            data.getJSONArray("authorized_profiles").getJSONObject(1).put(key, value)
            assertThrows(Exception::class.java) { PublicationProfiles.read(data) }
        }
        val data = settings()
        data.getJSONArray("authorized_profiles").getJSONObject(1).remove("profile_id")
        assertThrows(IllegalArgumentException::class.java) { PublicationProfiles.read(data) }
    }

    @Test fun deletedOrDisabledPrimaryCannotAuthorizeButCanBeShown() {
        val data = settings()
        data.getJSONArray("authorized_profiles").getJSONObject(0)
            .put("profile_id", JSONObject.NULL).put("enabled", false).put("ready", false)
        val profiles = PublicationProfiles.read(data)
        assertEquals(2, profiles.authorized.size)
        assertThrows(IllegalArgumentException::class.java) { profiles.requirePrimary(primary) }
        data.getJSONArray("authorized_profiles").getJSONObject(0).put("ready", true)
        assertThrows(IllegalArgumentException::class.java) { PublicationProfiles.read(data) }
    }

    @Test fun unavailableOrContradictoryPrimaryReadinessCannotStart() {
        for ((key, value) in listOf("ready" to false, "enabled" to false, "reason" to "DISABLED")) {
            val data = settings()
            data.getJSONArray("authorized_profiles").getJSONObject(0).put(key, value)
            assertThrows(IllegalArgumentException::class.java) {
                PublicationProviders.validate(job(), PublicationProfiles.read(data), primary)
            }
        }
    }

    @Test fun whatsappDestinationAndBatchChecksAreStillApplied() {
        for ((key, value) in listOf("page_name" to "Autre destination", "count" to 31,
            "due_at" to "2999-01-01T00:00:00Z", "web_triggered" to false)) {
            val input = job(); input.getJSONObject("payload").put(key, value)
            assertThrows(IllegalArgumentException::class.java) {
                PublicationProviders.validate(input, PublicationProfiles.read(settings()), primary)
            }
        }
    }

    @Test fun nextSettingsSnapshotImmediatelyDropsRemovedSecondaryGrant() {
        val data = settings()
        assertEquals(2, PublicationProfiles.read(data).authorized.size)
        data.getJSONArray("authorized_profiles").remove(1)
        assertEquals(listOf(primary), PublicationProfiles.read(data).authorized.map { it.profile })
    }
}
