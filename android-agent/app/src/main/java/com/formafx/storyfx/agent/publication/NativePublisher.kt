package com.formafx.storyfx.agent.publication

import android.content.Context
import android.content.Intent
import org.json.JSONObject

class NativePublisher(
    private val context: Context,
    private val ui: (() -> Unit) -> Unit,
    private val screen: () -> WhatsAppScreen,
    private val backToUpdates: () -> Unit,
    private val authorize: () -> Unit,
    private val journal: PublicationJournal
) {
    private fun action(operation: (WhatsAppScreen) -> Unit) {
        authorize()
        ui { operation(screen()) }
        Thread.sleep(1500)
    }

    fun execute(payload: JSONObject) {
        var uncertain = false
        try {
            val count = payload.getInt("count")
            val media = AlbumMedia.images(context, PublicationPolicy.album(payload), count)
            authorize()
            ui {
                val intent = requireNotNull(context.packageManager.getLaunchIntentForPackage(PublicationPolicy.provider))
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            Thread.sleep(2500)
            authorize()
            ui {
                if (!screen().hasUpdates()) {
                    check(screen().isOwnStatusList())
                    backToUpdates()
                }
            }
            Thread.sleep(1000)
            action { it.updates() }
            action { it.openOwnStatus() }
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
            ui { AlbumMedia.share(context, media) }
            Thread.sleep(2500)
            action { it.selectOwnStatus() }
            action { check(it.selectionIsOwnOnly()); it.send() }
            authorize()
            ui { check(screen().contactsPreview()) }
            // The encrypted reservation already contains NEEDS_REVIEW before this final action.
            uncertain = true
            action { check(it.contactsPreview()); it.send() }
            Thread.sleep(7000)
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
                    countVerified = if (page == 0 && visible == count) true else indexes != null && rows.size == count
                    if (!countVerified && indexes != null && rows.size < count) moved = current.scrollStatuses()
                }
                if (countVerified || !moved) break
                Thread.sleep(1000)
            }
            check(countVerified)
            journal.finish("CONFIRMED", "own_status_verified")
        } catch (_: Exception) {
            journal.finish(if (uncertain) "NEEDS_REVIEW" else "FAILED_BEFORE_PUBLICATION",
                if (uncertain) "result_uncertain" else "preflight_refused")
        }
    }
}
