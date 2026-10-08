package com.formafx.storyfx.agent.publication

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
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

/** Android binds the opted-in service during Direct Boot; private sessions stay in CE. */
class PublicationService : AccessibilityService() {
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var closed = false
    private var scheduled = false

    override fun onServiceConnected() {
        serviceInfo = serviceInfo.apply { flags = flags or AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS }
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
        val task = FutureTask {
            check(!closed && active && !locked() && EncryptedStore(this).publicationEnabled()); operation()
        }
        main.post(task)
        try { task.get(8, TimeUnit.SECONDS) } catch (failure: Exception) { task.cancel(false); throw failure }
    }

    private fun locked(): Boolean {
        val manager = getSystemService(KeyguardManager::class.java)
        val power = getSystemService(PowerManager::class.java)
        return manager.isDeviceLocked || manager.isKeyguardLocked || !power.isInteractive
    }

    private fun keyguardUi(operation: () -> Unit) {
        check(!closed && active)
        val task = FutureTask { check(!closed && active); operation() }
        main.post(task)
        try { task.get(8, TimeUnit.SECONDS) } catch (failure: Exception) { task.cancel(false); throw failure }
    }

    private fun attemptUnlock(api: AgentApi, store: EncryptedStore): Boolean {
        if (store.unlockAttempted() || store.unlockPin()?.also { it.fill('\u0000') } == null) return false
        val localTest = store.unlockTestPending()
        fun authorized(): Boolean {
            if (!localTest) return api.post("/v1/control/android/unlock-authorized", JSONObject()).getBoolean("authorized")
            val binding = api.post("/v1/control/android/settings", JSONObject()).optJSONObject("binding")
            return binding?.optString("profile") == store.publicationProfile() && binding?.optInt("enabled") == 1
        }
        if (localTest) store.consumeUnlockTest()
        return try { KeyguardUnlock(this, ::keyguardUi).attempt(store, ::authorized) }
            finally { if (localTest) store.rememberLocalUnlockResult() }
    }
    private fun contact(api: AgentApi, store: EncryptedStore): JSONObject {
        val physical = PublicationRuntime.physical(this, store.publicationEnabled(), active && !closed, !locked())
        var empty = false
        if (physical.globalEnabled && store.whatsAppPublicationEnabled() && physical.serviceReady && physical.screenUnlocked)
            runCatching { onUi { empty = WhatsAppScreen(ProviderWindow.root(this)).hasNoOwnStatus() } }
        val body = JSONObject()
        .put("service_ready", physical.serviceReady).put("media_ready", physical.mediaPermission)
        .put("screen_locked", !physical.screenUnlocked).put("own_status_empty", empty).put("native_runtime", physical.toJson())
        .put("app_version", BuildConfig.VERSION_NAME).put("battery_percent", getSystemService(BatteryManager::class.java)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).takeIf { it in 0..100 } ?: JSONObject.NULL)
        body.put("media_modes_ready", AlbumMedia.allowed(this) && AlbumMedia.videosAllowed(this))
        return PublicationHeartbeat(api, api::nativeRuntimeSupported).send(body)
    }

    private fun flush(api: AgentApi, journal: PublicationJournal) {
        PublicationReceipt(api, api::completionCompatibility).flush(journal)
    }

    private fun synchronize() {
        val boot = BootUnlockStore(this)
        if (!boot.userUnlocked()) {
            runCatching {
                val unlock = KeyguardUnlock(this, ::keyguardUi)
                if (boot.shouldInvoke() && active && !closed && unlock.bootChallengeReady(boot)) {
                    boot.reserveInvocation()
                    unlock.attempt(boot) { boot.unlockAllowed() && active && !closed }
                }
            }.onFailure { boot.saveUnlockResult(KeyguardResult.ERROR) }
            return
        }
        try {
            boot.restorePublicationPermissionAfterUnlock()
            val store = EncryptedStore(this)
            val session = store.session() ?: return
            val api = AgentApi(session.server, session.token)
            val journal = PublicationJournal(store)
            // A reboot acknowledges the reserved uncertain result; it never resumes provider gestures.
            flush(api, journal)
            // Availability can be reported while WhatsApp is off; the local global stop still forbids all gestures.
            var state = contact(api, store)
            if (!store.publicationEnabled() || !store.whatsAppPublicationEnabled()) return
            if (!locked() && store.unlockAttempted()) store.unlockSucceeded()
            if (!state.getBoolean("ready") && state.optString("reason") == "SCREEN_LOCKED" &&
                attemptUnlock(api, store)) state = contact(api, store)
            if (!state.getBoolean("ready")) {
                store.saveStatus(if (store.unlockAttempted()) "Déverrouillage non confirmé : déverrouillez manuellement. Aucun nouvel essai automatique."
                    else PublicationLabels.reason(state.optString("reason"))); return
            }
            val profiles = PublicationProfiles.read(api.post("/v1/control/android/settings", JSONObject()))
            profiles.requirePrimary(store.publicationProfile())
            val job = api.post("/v1/control/android/claim", JSONObject()).optJSONObject("job") ?: return
            if (!journal.reserve(job)) { flush(api, journal); return }
            val payload = try { PublicationProviders.validate(job, profiles, store.publicationProfile()) } catch (_: Exception) {
                journal.finish("FAILED_BEFORE_PUBLICATION", "preflight_refused"); flush(api, journal); return
            }
            val power = getSystemService(PowerManager::class.java)
            @Suppress("DEPRECATION")
            val awake = power.newWakeLock(PowerManager.SCREEN_DIM_WAKE_LOCK, "StoryFX:publication")
            awake.acquire(240000)
            try {
                val deadline = android.os.SystemClock.elapsedRealtime() + 210000
                NativePublicationRouter.execute(PublicationProvider.fromPlatform(payload.getString("platform")), payload) {
                    NativePublisher(this, ::onUi, { WhatsAppScreen(ProviderWindow.root(this)) { x, y ->
                    ProviderTap.perform(this, x, y)
                } }, {
                    onUi { ProviderPreparation.dismissShade(this) }
                }, {
                    check(!closed && active && store.publicationEnabled() && store.whatsAppPublicationEnabled() && !locked())
                    check(android.os.SystemClock.elapsedRealtime() < deadline)
                    check(contact(api, store).getBoolean("ready"))
                    check(api.post("/v1/control/android/jobs/${job.getString("id")}/ready", JSONObject()).getBoolean("authorized"))
                }, journal, deadline)
                }
            } finally { if (awake.isHeld) awake.release() }
            flush(api, journal)
            store.saveStatus("Résultat Android enregistré ; consultez les rapports du tableau de bord.")
        } catch (failure: Exception) {
            runCatching { EncryptedStore(this).saveStatus(if (failure is AgentRequestException && failure.status in listOf(401, 403))
                "Accès refusé : vérifiez la connexion FormaFX." else "Pilotage Android en attente. Aucun geste de publication rejoué.") }
        }
    }
    override fun dump(fd: java.io.FileDescriptor?, writer: java.io.PrintWriter?, args: Array<out String>?) {
        val root = rootInActiveWindow
        val kind = when (root?.packageName?.toString()) {
            PublicationPolicy.provider -> "provider"
            KeyguardShape.system -> "system_ui"
            null -> "unavailable"
            else -> "other"
        }
        val boot = BootUnlockStore(this)
        val result = JSONObject().put("app_version", BuildConfig.VERSION_NAME).put("service_ready", active)
            .put("boot_unlock", boot.diagnostics())
            .put("screen_locked", locked()).put("active_root_kind", kind)
            .put("provider_layout_nodes_enabled", serviceInfo.flags and AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS != 0)
            .put("provider_tap_capable", serviceInfo.capabilities and AccessibilityServiceInfo.CAPABILITY_CAN_PERFORM_GESTURES != 0)
        if (boot.userUnlocked()) result.put("unlock_result", EncryptedStore(this).unlockResult())
            .put("local_unlock_result", EncryptedStore(this).localUnlockResult())
            .put("unlock_failure", EncryptedStore(this).unlockFailure())
            .put("local_test_pending", EncryptedStore(this).unlockTestPending())
            .put("unlock_credential_present", EncryptedStore(this).unlockPin()?.also { it.fill('\u0000') } != null)
            .put("unlock_attempted", EncryptedStore(this).unlockAttempted())
            .put("whatsapp", WhatsAppScreen(ProviderWindow.root(this)).homeEvidence())
            .put("keyguard", KeyguardUnlock(this, ::keyguardUi).diagnostics())
        writer?.println("storyfx_diagnostic=" + result.toString())
    }
    companion object { @Volatile var active = false; private set }
}
