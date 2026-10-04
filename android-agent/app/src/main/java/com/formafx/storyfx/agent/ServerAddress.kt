package com.formafx.storyfx.agent

import java.net.URI

object ServerAddress {
    fun validate(value: String, debug: Boolean): String {
        val uri = try { URI(value.trim()) } catch (_: Exception) { invalid() }
        val host = uri.host?.lowercase() ?: invalid()
        val emulator = debug && uri.scheme == "http" && host == "10.0.2.2"
        if (uri.scheme != "https" && !emulator) invalid()
        if (uri.userInfo != null || uri.query != null || uri.fragment != null) invalid()
        if (!uri.path.isNullOrEmpty() && uri.path != "/") invalid()
        if (uri.port == 0 || uri.port > 65535 || uri.port < -1) invalid()
        if (host == "localhost" || host.endsWith(".localhost")) invalid()
        return uri.toASCIIString().trimEnd('/')
    }

    private fun invalid(): Nothing = throw IllegalArgumentException(
        "Saisissez l’adresse HTTPS racine du serveur."
    )
}
