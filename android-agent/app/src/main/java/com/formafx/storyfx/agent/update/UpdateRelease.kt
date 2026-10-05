package com.formafx.storyfx.agent.update

import org.json.JSONObject
import java.net.URI

data class UpdateRelease(val version: String, val code: Long, val url: String, val sha256: String) {
    companion object {
        const val catalog = "https://api.formafx.com/functions/v1/storyfx-agent-download?" +
            "platform=storyfx_agent_android&channel=stable&version=latest&asset_type=apk&metadata=1"
        fun parse(body: String): UpdateRelease {
            val json = JSONObject(body)
            require(json.getString("platform") == "storyfx_agent_android")
            val version = json.getString("version")
            val code = json.getLong("version_code")
            require(Regex("[0-9]+\\.[0-9]+\\.[0-9]+").matches(version) && code > 0)
            val url = json.getString("download_url")
            val uri = URI(url)
            require(uri.scheme == "https" && uri.host == "api.formafx.com" &&
                uri.port in listOf(-1, 443) && uri.rawUserInfo == null &&
                uri.rawQuery == null && uri.rawFragment == null)
            require(uri.rawPath == "/downloads/storyfx-android/StoryFX-Android-$version-v$code.apk")
            val hash = json.getString("sha256").lowercase()
            require(Regex("[a-f0-9]{64}").matches(hash))
            return UpdateRelease(version, code, url, hash)
        }
    }
}
