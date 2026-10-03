package com.formafx.storyfx.agent

import org.json.JSONObject
import java.time.OffsetDateTime
import java.util.UUID

interface AgentAuthStateStore {
    fun pendingAuth(): PendingAgentAuth?
    fun savePendingAuth(value: PendingAgentAuth)
    fun associationPresent(): Boolean
    fun pendingEventsPresent(): Boolean
    fun saveAuthenticatedSession(value: AuthenticatedAgentSession)
}

class AuthenticatedAgentSession(
    val server: String, val deviceId: String, val token: String,
    val userId: String, val email: String,
)

class AgentAuthProtocol(
    private val gateway: AgentGateway,
    private val store: AgentAuthStateStore,
    private val debug: Boolean,
    private val now: () -> Long = System::currentTimeMillis,
) {
    fun start(server: String, installationId: String, name: String,
              androidVersion: String, appVersion: String): String {
        if (store.associationPresent()) throw AgentAuthException("already_associated")
        if (store.pendingEventsPresent()) throw AgentAuthException("pending_diagnostics")
        UUID.fromString(installationId)
        val address = ServerAddress.validate(server, debug)
        if (!debug && address != AgentAuthRoutes.publicServer) throw AgentAuthException("invalid_server")
        require(name.trim().isNotEmpty())
        val pending = AgentAuthProof.create(address, installationId, now())
        store.savePendingAuth(pending)
        val response = gateway.post("/v1/auth/agent/start", JSONObject()
            .put("installation_id", installationId).put("name", name.trim().take(80))
            .put("android_version", androidVersion).put("app_version", appVersion)
            .put("state", pending.state).put("device_nonce", pending.deviceNonce)
            .put("code_challenge", pending.challenge()).put("code_challenge_method", "S256")
            .put("redirect_uri", AgentAuthRoutes.callback))
        val url = AgentAuthRoutes.validateConnectUrl(response.getString("connect_url"), address, debug)
        val expiresAt = OffsetDateTime.parse(response.getString("expires_at")).toInstant().toEpochMilli()
        if (expiresAt <= now() || expiresAt > now() + 900_000) throw AgentAuthException("expired_login")
        store.savePendingAuth(pending.withExpiration(expiresAt))
        return url
    }

    fun complete(callback: String): String {
        val pending = store.pendingAuth() ?: throw AgentAuthException("missing_login")
        if (pending.expiresAt <= now()) throw AgentAuthException("expired_login")
        if (store.associationPresent()) throw AgentAuthException("already_associated")
        if (store.pendingEventsPresent()) throw AgentAuthException("pending_diagnostics")
        val received = AgentAuthRoutes.parseCallback(callback)
        if (!AgentAuthProof.stateMatches(pending.state, received.state)) {
            throw AgentAuthException("state_mismatch")
        }
        ServerAddress.validate(pending.server, debug)
        if (!debug && pending.server != AgentAuthRoutes.publicServer) throw AgentAuthException("invalid_server")
        val response = gateway.post("/v1/auth/agent/exchange", JSONObject()
            .put("ticket", received.ticket).put("state", pending.state)
            .put("device_nonce", pending.deviceNonce).put("installation_id", pending.installationId)
            .put("code_verifier", pending.verifier))
        val deviceId = response.getString("device_id"); UUID.fromString(deviceId)
        val token = response.getString("token")
        if (token.length !in 16..8192 || token.any { it.isWhitespace() || it.isISOControl() }) {
            throw AgentAuthException("invalid_session")
        }
        val user = response.getJSONObject("user")
        val userId = user.getString("id"); UUID.fromString(userId)
        val email = user.getString("email")
        if (email.length !in 3..254 || !email.contains('@') || email.any { it.isISOControl() }) {
            throw AgentAuthException("invalid_session")
        }
        store.saveAuthenticatedSession(AuthenticatedAgentSession(
            pending.server, deviceId, token, userId, email))
        return "Compte FormaFX connecté • téléphone associé"
    }
}
