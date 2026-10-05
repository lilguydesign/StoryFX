package com.formafx.storyfx.agent.update

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class UpdateReleaseTest {
    private fun payload(): JSONObject = JSONObject().put("platform", "storyfx_agent_android")
        .put("version", "0.3.0").put("version_code", 3)
        .put("download_url", "https://api.formafx.com/downloads/storyfx-android/StoryFX-Android-0.3.0-v3.apk")
        .put("sha256", "a".repeat(64))
    @Test fun acceptsOfficialRelease() { assertEquals(3L, UpdateRelease.parse(payload().toString()).code) }
    @Test(expected = IllegalArgumentException::class) fun refusesOtherHost() {
        UpdateRelease.parse(payload().put("download_url", "https://example.com/update.apk").toString())
    }
    @Test(expected = IllegalArgumentException::class) fun refusesVersionMismatch() {
        UpdateRelease.parse(payload().put("version_code", 4).toString())
    }
    @Test(expected = IllegalArgumentException::class) fun refusesMissingDigest() {
        UpdateRelease.parse(payload().put("sha256", "").toString())
    }
    @Test(expected = IllegalArgumentException::class) fun refusesRedirectParameters() {
        val data = payload(); data.put("download_url", data.getString("download_url") + "?next=external")
        UpdateRelease.parse(data.toString())
    }
    @Test(expected = IllegalArgumentException::class) fun refusesOtherApplication() {
        UpdateRelease.parse(payload().put("platform", "other_android").toString())
    }
}
