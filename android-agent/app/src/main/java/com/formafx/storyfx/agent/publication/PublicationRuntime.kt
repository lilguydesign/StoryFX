package com.formafx.storyfx.agent.publication

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.formafx.storyfx.agent.BuildConfig
import org.json.JSONObject

object PublicationRuntime {
    fun snapshot(context: Context) = JSONObject().put("app_version", BuildConfig.VERSION_NAME)
        .put("service_ready", PublicationService.active).put("network", network(context))

    private fun network(context: Context): String = runCatching {
        val manager = context.getSystemService(ConnectivityManager::class.java)
        val active = manager.activeNetwork ?: return@runCatching "offline"
        val capabilities = manager.getNetworkCapabilities(active) ?: return@runCatching "unknown"
        when {
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            else -> "other"
        }
    }.getOrDefault("unknown")
}
