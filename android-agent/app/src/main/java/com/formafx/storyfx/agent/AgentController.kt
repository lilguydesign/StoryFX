package com.formafx.storyfx.agent

import android.app.KeyguardManager
import android.content.Context
import android.os.BatteryManager
import android.os.Build
import org.json.JSONObject
import java.text.DateFormat
import java.util.Date
import java.util.UUID

object AgentController {
    private val lock = Any()

    fun phoneName(): String {
        val model = Build.MODEL.orEmpty()
        val brand = Build.MANUFACTURER.orEmpty()
        return if (model.startsWith(brand, ignoreCase = true)) model else "$brand $model"
    }

    fun enroll(context: Context, address: String, code: String, name: String): String =
        synchronized(lock) {
            val server = ServerAddress.validate(address, BuildConfig.DEBUG)
            require(code.isNotBlank() && name.trim().isNotBlank())
            val store = EncryptedStore(context)
            check(store.session() == null)
            val response = AgentApi(server).post("/v1/devices/enroll", JSONObject()
                .put("code", code.trim()).put("installation_id", store.installationId())
                .put("name", name.trim().take(80)).put("android_version", Build.VERSION.RELEASE))
            val id = response.getString("device_id")
            UUID.fromString(id)
            val token = response.getString("token")
            check(token.isNotBlank() && token.length <= 8192)
            store.saveSession(server, id, token)
            AgentSchedule.enable(context)
            "Téléphone associé • prêt pour un diagnostic".also { store.saveStatus(it) }
        }

    fun synchronize(context: Context): String = synchronized(lock) {
        val store = EncryptedStore(context)
        val session = store.session() ?: throw IllegalStateException("Association requise")
        val battery = context.getSystemService(BatteryManager::class.java)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).takeIf { it in 0..100 }
        val keyguard = context.getSystemService(KeyguardManager::class.java)
        val heartbeat = JSONObject().put("battery_percent", battery ?: JSONObject.NULL)
            .put("screen_locked", keyguard.isDeviceLocked || keyguard.isKeyguardLocked)
            .put("app_version", BuildConfig.VERSION_NAME).put("executor", "diagnostic")
        val result = DiagnosticRunner(AgentApi(session.server, session.token), store)
            .synchronize(session.deviceId, heartbeat)
        val time = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date())
        "$result\nDernière synchronisation : $time".also { store.saveStatus(it) }
    }

    fun erase(context: Context) = synchronized(lock) {
        AgentSchedule.disable(context)
        EncryptedStore(context).eraseAssociation()
    }

    fun recordFailure(context: Context, failure: Exception): String {
        val message = when (failure) {
            is AgentRequestException -> when (failure.status) {
                401, 403 -> "Association refusée ou révoquée. Vérifiez le tableau de bord."
                429 -> "Serveur occupé. La synchronisation sera retentée."
                else -> "Serveur indisponible (HTTP ${failure.status}). Événements conservés."
            }
            is IllegalArgumentException -> "Vérifiez l’adresse HTTPS et les informations d’association."
            else -> "Synchronisation indisponible. Les événements en attente restent conservés."
        }
        runCatching { EncryptedStore(context).saveStatus(message) }
        return message
    }
}
