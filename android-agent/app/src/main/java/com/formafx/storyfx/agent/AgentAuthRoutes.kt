package com.formafx.storyfx.agent

import java.net.URI
import java.net.URLDecoder

class AgentAuthCallback(val ticket: String, val state: String)

object AgentAuthRoutes {
    const val callback = "storyfx-android://auth/callback"
    const val publicServer = "https://story.formafx.com"
    private val opaque = Regex("[A-Za-z0-9_-]{16,512}")
    private val statePattern = Regex("[A-Za-z0-9_-]{43}")

    fun parseCallback(value: String): AgentAuthCallback {
        val uri = parse(value)
        if (uri.scheme != "storyfx-android" || uri.rawAuthority != "auth" ||
            uri.rawPath != "/callback" || uri.fragment != null) invalid()
        val fields = query(uri)
        if (fields.keys != setOf("ticket", "state")) invalid()
        val ticket = fields.getValue("ticket")
        val state = fields.getValue("state")
        if (!opaque.matches(ticket) || !statePattern.matches(state)) invalid()
        return AgentAuthCallback(ticket, state)
    }

    fun validateConnectUrl(value: String, server: String, debug: Boolean): String {
        val base = URI(ServerAddress.validate(server, debug))
        val uri = parse(value)
        if (uri.scheme != base.scheme || uri.host != base.host || uri.port != base.port ||
            uri.userInfo != null || uri.rawPath != "/agent/connect" || uri.fragment != null) invalid()
        val fields = query(uri)
        if (fields.keys != setOf("request_id") || !opaque.matches(fields.getValue("request_id"))) invalid()
        return uri.toASCIIString()
    }

    private fun parse(value: String): URI {
        if (value.length > 4096) invalid()
        return try { URI(value) } catch (_: Exception) { invalid() }
    }

    private fun query(uri: URI): Map<String, String> {
        val raw = uri.rawQuery ?: invalid()
        val result = linkedMapOf<String, String>()
        for (part in raw.split('&')) {
            val pieces = part.split('=', limit = 2)
            if (pieces.size != 2) invalid()
            val key = decode(pieces[0]); val value = decode(pieces[1])
            if (result.put(key, value) != null) invalid()
        }
        return result
    }

    private fun decode(value: String): String = try {
        URLDecoder.decode(value, Charsets.UTF_8.name())
    } catch (_: Exception) { invalid() }

    private fun invalid(): Nothing = throw AgentAuthException("invalid_callback")
}

class AgentAuthException(val safeCode: String) : Exception("Connexion FormaFX non valide.")
