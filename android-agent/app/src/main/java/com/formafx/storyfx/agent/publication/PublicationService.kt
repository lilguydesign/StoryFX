package com.formafx.storyfx.agent.publication

import android.accessibilityservice.AccessibilityService
import android.app.KeyguardManager
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.BatteryManager
import android.view.accessibility.AccessibilityEvent
import com.formafx.storyfx.agent.AgentApi
import com.formafx.storyfx.agent.AgentRequestException
import com.formafx.storyfx.agent.EncryptedStore
import com.formafx.storyfx.agent.BuildConfig
import org.json.JSONObject
import java.util.concurrent.FutureTask
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Android binds this opt-in service again after reboot and the first device unlock. */
class PublicationService : AccessibilityService() {
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private val main = Handler(Looper.getMainLooper())
    private var closed = false
    private var scheduled = false

    override fun onServiceConnected() {
        active = true
        if (!scheduled) { scheduled = true; worker.scheduleWithFixedDelay({ synchronize() }, 0, 20, TimeUnit.SECONDS) }
    }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) { /* No screen-event logging. */ }
    override fun onInterrupt() { active = false }
    override fun onDestroy() {
        closed = true; active = false; worker.shutdownNow(); super.onDestroy()
    }

    private fun onUi(operation: () -> Unit) {
        check(!closed)
        val task = FutureTask { check(!closed && active && !locked()); operation() }
        main.post(task)
        try { task.get(8, TimeUnit.SECONDS) } catch (failure: Exception) { task.cancel(false); throw failure }
    }

    private fun locked(): Boolean {
        val manager = getSystemService(KeyguardManager::class.java)
        val power = getSystemService(PowerManager::class.java)
        return manager.isDeviceLocked || manager.isKeyguardLocked || !power.isInteractive
    }
    private fun contact(api: AgentApi): JSONObject = api.post("/v1/control/android/heartbeat", JSONObject()
        .put("service_ready", active).put("media_ready", AlbumMedia.allowed(this)).put("screen_locked", locked())
        .put("app_version", BuildConfig.VERSION_NAME).put("battery_percent", getSystemService(BatteryManager::class.java)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).takeIf { it in 0..100 } ?: JSONObject.NULL))

    private fun flush(api: AgentApi, journal: PublicationJournal) {
        val pending = journal.pending() ?: return
        api.post("/v1/control/android/jobs/${pending.getString("job_id")}/complete", JSONObject()
            .put("state", pending.getString("state")).put("evidence", pending.getString("evidence")))
        journal.acknowledged()
    }

    private fun synchronize() {
        try {
            val store = EncryptedStore(this)
            val session = store.session() ?: return
            val api = AgentApi(session.server, session.token)
            val journal = PublicationJournal(store)
            // A reboot acknowledges the reserved uncertain result; it never resumes provider gestures.
            flush(api, journal)
            if (!store.publicationEnabled()) return
            val state = contact(api)
            if (!state.getBoolean("ready")) {
                store.saveStatus(PublicationLabels.reason(state.optString("reason"))); return
            }
            val job = api.post("/v1/control/android/claim", JSONObject()).optJSONObject("job") ?: return
            if (!journal.reserve(job)) { flush(api, journal); return }
            val payload = try { PublicationPolicy.validate(job, store.publicationProfile()) } catch (_: Exception) {
                journal.finish("FAILED_BEFORE_PUBLICATION", "preflight_refused"); flush(api, journal); return
            }
            val power = getSystemService(PowerManager::class.java)
            @Suppress("DEPRECATION")
            val awake = power.newWakeLock(PowerManager.SCREEN_DIM_WAKE_LOCK, "StoryFX:publication")
            awake.acquire(150000)
            try {
                val deadline = android.os.SystemClock.elapsedRealtime() + 120000
                NativePublisher(this, ::onUi, { WhatsAppScreen(rootInActiveWindow) }, {
                    check(!closed && active && store.publicationEnabled() && !locked())
                    check(android.os.SystemClock.elapsedRealtime() < deadline)
                    check(contact(api).getBoolean("ready"))
                    check(api.post("/v1/control/android/jobs/${job.getString("id")}/ready", JSONObject()).getBoolean("authorized"))
                }, journal).execute(payload)
            } finally { if (awake.isHeld) awake.release() }
            flush(api, journal)
            store.saveStatus("Résultat Android enregistré ; consultez les rapports du tableau de bord.")
        } catch (failure: Exception) {
            runCatching { EncryptedStore(this).saveStatus(if (failure is AgentRequestException && failure.status in listOf(401, 403))
                "Accès refusé : vérifiez la connexion FormaFX." else "Pilotage Android en attente. Aucun geste de publication rejoué.") }
        }
    }
    companion object { @Volatile var active = false; private set }
}
