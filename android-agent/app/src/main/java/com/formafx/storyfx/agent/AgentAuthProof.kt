package com.formafx.storyfx.agent

import org.json.JSONObject
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64

class PendingAgentAuth(
    val server: String,
    val installationId: String,
    val state: String,
    val deviceNonce: String,
    val verifier: String,
    val expiresAt: Long,
) {
    fun challenge(): String = AgentAuthProof.encode(
        MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII)))

    fun toJson(): String = JSONObject().put("server", server).put("installation_id", installationId)
        .put("state", state).put("device_nonce", deviceNonce).put("verifier", verifier)
        .put("expires_at", expiresAt).toString()

    fun withExpiration(value: Long): PendingAgentAuth = PendingAgentAuth(
        server, installationId, state, deviceNonce, verifier, value)

    companion object {
        fun fromJson(value: String): PendingAgentAuth {
            val objectValue = JSONObject(value)
            return PendingAgentAuth(objectValue.getString("server"),
                objectValue.getString("installation_id"), objectValue.getString("state"),
                objectValue.getString("device_nonce"), objectValue.getString("verifier"),
                objectValue.getLong("expires_at"))
        }
    }
}

object AgentAuthProof {
    fun create(server: String, installationId: String, now: Long): PendingAgentAuth =
        PendingAgentAuth(server, installationId, random(32), random(32), random(64), now + 600_000)

    fun stateMatches(expected: String, received: String): Boolean = MessageDigest.isEqual(
        expected.toByteArray(Charsets.US_ASCII), received.toByteArray(Charsets.US_ASCII))

    internal fun encode(bytes: ByteArray): String = Base64.getUrlEncoder().withoutPadding()
        .encodeToString(bytes)

    private fun random(size: Int): String = encode(ByteArray(size).apply {
        SecureRandom().nextBytes(this)
    })
}
