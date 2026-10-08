package com.formafx.storyfx.agent.publication

import android.content.Context
import android.content.Intent
import org.json.JSONObject

class NativePublisher(
    private val context: Context,
    private val ui: (() -> Unit) -> Unit,
    private val screen: () -> WhatsAppScreen,
    private val prepareProvider: () -> Unit,
    private val authorize: () -> Unit,
    private val journal: PublicationJournal,
    private val deadlineMillis: Long
) : NativePublicationAdapter {
    override val provider = PublicationProvider.WHATSAPP_BUSINESS
    private val diagnostics = PublicationDiagnostics()
    private fun inspect(operation: (WhatsAppScreen) -> Unit) = ui {
        val current = screen()
        diagnostics.provider = current.correctPackage
        diagnostics.ownLabels = current.ownLabelCount()
        diagnostics.navigation = when (current.navigationState()) {
            OwnScreen.OWN_LIST -> "own_list"
            OwnScreen.OWN_HOME, OwnScreen.EMPTY_HOME -> "updates_home"
            OwnScreen.UPDATES_TAB -> "updates_tab"
            else -> if (current.correctPackage) "unknown" else "provider_pending"
        }
        operation(current)
    }

    private fun action(guard: () -> Unit = authorize, operation: (WhatsAppScreen) -> Unit) {
        guard()
        inspect(operation)
        Thread.sleep(1500)
    }

    private fun await(predicate: (WhatsAppScreen) -> Boolean) {
        repeat(20) {
            authorize()
            var ready = false
            inspect { ready = predicate(it) }
            if (ready) return
            Thread.sleep(500)
        }
        error("PROVIDER_SCREEN_TIMEOUT")
    }

    private fun verificationGuard() {
        check(android.os.SystemClock.elapsedRealtime() < deadlineMillis)
        authorize()
        check(android.os.SystemClock.elapsedRealtime() < deadlineMillis)
    }

    private fun openOwn(waitForUpload: Boolean = false, beforeOwn: () -> Unit = {}) = PublicationNavigation({
        var state = OwnScreen.UNKNOWN
        inspect { state = it.navigationState() }
        state
    }, { action(if (waitForUpload) ::verificationGuard else authorize) { it.updates() } },
        { action(if (waitForUpload) ::verificationGuard else authorize) { it.ownStatus() } },
        if (waitForUpload) ::verificationGuard else authorize,
        maxObservations = if (waitForUpload) Int.MAX_VALUE else 20,
        withinDeadline = { android.os.SystemClock.elapsedRealtime() < deadlineMillis }
    ).openOwn(beforeOwn).also { state ->
        if (state == OwnScreen.OWN_LIST) PublicationListPosition.reset({
            var moved = false
            inspect { moved = it.scrollStatusesBack() }
            moved
        }, if (waitForUpload) ::verificationGuard else authorize)
    }

    override fun execute(payload: JSONObject) {
        val progress = PublicationProgress()
        fun stage(value: String) {
            progress.enter(value); diagnostics.stage = value
            journal.recordDiagnostics(diagnostics.snapshot(PublicationRuntime.snapshot(context)))
        }
        fun finish(state: String, evidence: String) = journal.finish(state, evidence,
            diagnostics.snapshot(PublicationRuntime.snapshot(context)))
        try {
            val count = MediaPlan.total(payload)
            diagnostics.expected = count
            val media = AlbumMedia.batch(context, payload)
            diagnostics.selected = media.size
            stage("provider_not_ready")
            authorize()
            prepareProvider()
            ui {
                val intent = requireNotNull(context.packageManager.getLaunchIntentForPackage(PublicationPolicy.provider))
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP))
            }
            Thread.sleep(2500)
            authorize()
            stage("updates_navigation_failed")
            openOwn { stage("own_status_unavailable") }
            // A fresh own-status baseline must have no recent statuses to confuse with this job.
            var baselineReady = false
            for (attempt in 0 until 45) {
                authorize()
                var recent = -1
                inspect { recent = it.recentCount() }
                if (recent == 0) { baselineReady = true; break }
                Thread.sleep(2000)
            }
            check(baselineReady)
            inspect { check(it.recentCount() == 0) }
            authorize()
            stage("share_selection_refused")
            ui { AlbumMedia.share(context, media) }
            await { it.ownPickerReady() }
            action { it.selectOwnStatus() }
            // Even the picker arrow may change behavior in a future provider version.
            // A missing preview after this action must never authorize an automatic replay.
            progress.beforeProviderSend()
            action { check(it.selectionIsOwnOnly()); it.send() }
            authorize()
            stage("contacts_preview_refused")
            await { it.contactsPreview() }
            // The encrypted reservation already contains NEEDS_REVIEW before this final action.
            progress.beforeProviderSend()
            action { check(it.contactsPreview()); it.send() }
            stage("own_status_verification")
            Thread.sleep(7000)
            diagnostics.beginVerification()
            journal.recordDiagnostics(diagnostics.snapshot(PublicationRuntime.snapshot(context)))
            PublicationVerification(deadlineMillis, android.os.SystemClock::elapsedRealtime, authorize).verify(count,
                restart = { openOwn(waitForUpload = true) },
                observe = {
                    var completed = emptyList<Int?>()
                    inspect { completed = it.verifiedRecentRows() }
                    completed
                }, scroll = {
                    var moved = false
                    inspect { moved = it.scrollStatuses() }
                    moved
                }, record = diagnostics::observeVerification)
            finish("CONFIRMED", "own_status_verified")
        } catch (_: Exception) {
            val (state, evidence) = progress.failure()
            finish(state, evidence)
        }
    }
}
