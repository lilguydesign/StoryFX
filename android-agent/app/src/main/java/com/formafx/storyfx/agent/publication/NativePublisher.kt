package com.formafx.storyfx.agent.publication

import android.content.Context
import android.content.Intent
import org.json.JSONObject

class NativePublisher(
    private val context: Context,
    private val ui: (() -> Unit) -> Unit,
    private val screen: () -> WhatsAppScreen,
    private val backToUpdates: () -> Unit,
    private val prepareProvider: () -> Unit,
    private val authorize: () -> Unit,
    private val journal: PublicationJournal
) {
    private fun action(operation: (WhatsAppScreen) -> Unit) {
        authorize()
        ui { operation(screen()) }
        Thread.sleep(1500)
    }

    fun execute(payload: JSONObject) {
        val progress = PublicationProgress()
        try {
            val count = MediaPlan.total(payload)
            val media = AlbumMedia.batch(context, payload)
            progress.enter("provider_not_ready")
            authorize()
            prepareProvider()
            ui {
                val intent = requireNotNull(context.packageManager.getLaunchIntentForPackage(PublicationPolicy.provider))
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP))
            }
            Thread.sleep(2500)
            authorize()
            progress.enter("updates_navigation_failed")
            ui {
                if (!screen().hasNoOwnStatus() && !screen().hasUpdates()) {
                    check(screen().isOwnStatusList())
                    backToUpdates()
                }
            }
            Thread.sleep(1000)
            action { if (!it.hasNoOwnStatus()) it.updates() }
            progress.enter("own_status_unavailable")
            action { it.openOwnStatus() }
            var baselineTotal: Int? = null
            ui { val current = screen(); baselineTotal = if (current.hasNoOwnStatus()) 0 else current.statusCount() }
            // A fresh own-status baseline must have no recent statuses to confuse with this job.
            var baselineReady = false
            for (attempt in 0 until 45) {
                authorize()
                var recent = -1
                ui { recent = screen().recentCount() }
                if (recent == 0) { baselineReady = true; break }
                Thread.sleep(2000)
            }
            check(baselineReady)
            ui { check(screen().recentCount() == 0) }
            authorize()
            progress.enter("share_selection_refused")
            ui { AlbumMedia.share(context, media) }
            Thread.sleep(2500)
            action { it.selectOwnStatus() }
            // Even the picker arrow may change behavior in a future provider version.
            // A missing preview after this action must never authorize an automatic replay.
            progress.beforeProviderSend()
            action { check(it.selectionIsOwnOnly()); it.send() }
            authorize()
            progress.enter("contacts_preview_refused")
            ui { check(screen().contactsPreview()) }
            // The encrypted reservation already contains NEEDS_REVIEW before this final action.
            progress.beforeProviderSend()
            action { check(it.contactsPreview()); it.send() }
            Thread.sleep(7000)
            // Provider uploads can finish before its own-status target appears.
            // Read only until the exact target is ready; never repeat the send.
            var ownReady = false
            for (attempt in 0 until 20) {
                authorize()
                ui { ownReady = screen().ownStatusReady() }
                if (ownReady) break
                Thread.sleep(1500)
            }
            check(ownReady)
            action { it.openOwnStatus() }
            val rows = mutableSetOf<Int>()
            var countVerified = false
            for (page in 0 until 8) {
                authorize()
                var moved = false
                ui {
                    val current = screen()
                    val visible = current.recentCount()
                    val indexes = current.recentRows()
                    if (indexes != null) rows.addAll(indexes)
                    countVerified = PublicationCountDelta.matches(baselineTotal, current.statusCount(), count) ||
                        if (page == 0 && visible == count) true else indexes != null && rows.size == count
                    if (!countVerified && indexes != null && rows.size < count) moved = current.scrollStatuses()
                }
                if (countVerified || !moved) break
                Thread.sleep(1000)
            }
            check(countVerified)
            journal.finish("CONFIRMED", "own_status_verified")
        } catch (_: Exception) {
            val (state, evidence) = progress.failure()
            journal.finish(state, evidence)
        }
    }
}
