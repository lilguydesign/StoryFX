package com.formafx.storyfx.agent.publication

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.content.ComponentName
import android.provider.Settings
import com.formafx.storyfx.agent.BuildConfig
import org.json.JSONObject

object PublicationRuntime {
    fun physical(context: Context, globalEnabled: Boolean, serviceActive: Boolean, screenUnlocked: Boolean): NativeRuntimeState {
        val expected = ComponentName(context, PublicationService::class.java)
        val accessibility = Settings.Secure.getInt(context.contentResolver, Settings.Secure.ACCESSIBILITY_ENABLED, 0) == 1 &&
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
                .orEmpty().split(':').any { ComponentName.unflattenFromString(it) == expected }
        return NativeRuntimeState(globalEnabled, serviceActive && accessibility, accessibility,
            screenUnlocked, AlbumMedia.allowed(context))
    }

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
