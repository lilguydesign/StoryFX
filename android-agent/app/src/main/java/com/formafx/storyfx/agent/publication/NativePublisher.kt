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
    private val journal: PublicationJournal
) {
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

    private fun action(operation: (WhatsAppScreen) -> Unit) {
        authorize()
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

    private fun openOwn(beforeOwn: () -> Unit = {}) = PublicationNavigation({
        var state = OwnScreen.UNKNOWN
        inspect { state = it.navigationState() }
        state
    }, { action { it.updates() } }, { action { it.ownStatus() } }, authorize).openOwn(beforeOwn).also { state ->
        if (state == OwnScreen.OWN_LIST) PublicationListPosition.reset({
            var moved = false
            inspect { moved = it.scrollStatusesBack() }
            moved
        }, authorize)
    }

    fun execute(payload: JSONObject) {
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
            // Provider uploads can finish before its own-status target appears.
            // Read only until the exact target is ready; never repeat the send.
            openOwn()
            val rows = mutableSetOf<Int>()
            var countVerified = false
            for (page in 0 until 8) {
                authorize()
                var moved = false
                inspect { current ->
                    val verified = current.verifiedRecentRows()
                    rows.addAll(verified.filterNotNull())
                    diagnostics.verification = PublicationProof.verified(count, verified.size, rows)
                    countVerified = diagnostics.verification != "none"
                    diagnostics.verified = if (countVerified) count else maxOf(verified.size, rows.size).coerceAtMost(30)
                    if (!countVerified && verified.isNotEmpty() && verified.all { it != null } && rows.size < count)
                        moved = current.scrollStatuses()
                }
                if (countVerified || !moved) break
                Thread.sleep(1000)
            }
            check(countVerified)
            finish("CONFIRMED", "own_status_verified")
        } catch (_: Exception) {
            val (state, evidence) = progress.failure()
            finish(state, evidence)
        }
    }
}
