package com.formafx.storyfx.agent.publication

import android.os.Build
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONObject

/** Read-only structure for explicit dumps and manual slice baselines. No persisted IDs. */
object NativeStatusObservation {
    fun capture(root: AccessibilityNodeInfo?): JSONObject = try {
        val provider = root?.packageName?.toString() == PublicationPolicy.provider
        val nodes = mutableListOf<OwnStatusObservation.Node>()
        var complete = true
        fun walk(node: AccessibilityNodeInfo, parent: Int?, depth: Int) {
            if (nodes.size >= 2500 || depth > 128) { complete = false; return }
            if (node.packageName?.toString() != PublicationPolicy.provider) return
            val index = nodes.size
            val text = node.text?.toString().orEmpty()
            val description = node.contentDescription?.toString().orEmpty()
            val resource = node.viewIdResourceName.orEmpty()
            val className = node.className?.toString().orEmpty()
            val actions = node.actionList.map { it.id }
            nodes.add(OwnStatusObservation.Node(parent, node.isVisibleToUser,
                className.endsWith("ListView") || className.endsWith("RecyclerView"), node.isScrollable,
                AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD in actions,
                AccessibilityNodeInfo.ACTION_SCROLL_FORWARD in actions,
                resource == "${PublicationPolicy.provider}:id/date_time", OwnStatusObservation.timeClass(text),
                Regex("\\d+ (views?|vues?)", RegexOption.IGNORE_CASE).matches(text),
                PublicationProof.pending(text, description), node.collectionItemInfo?.rowIndex,
                node.collectionInfo?.rowCount, node.collectionInfo?.columnCount,
                if (Build.VERSION.SDK_INT >= 33) OwnStatusObservation.uniqueIdPresent(Build.VERSION.SDK_INT) { node.uniqueId }
                    else false,
                PublicationScreenLabels.own(text, description),
                resource in setOf("${PublicationPolicy.provider}:id/playback_progress", "${PublicationPolicy.provider}:id/playback_pager"),
                resource == "${PublicationPolicy.provider}:id/send"))
            for (childIndex in 0 until node.childCount) {
                val child = node.getChild(childIndex)
                if (child == null) complete = false else walk(child, index, depth + 1)
                if (nodes.size >= 2500) { complete = false; break }
            }
        }
        if (provider && root != null) walk(root, null, 0)
        val recognized = provider && complete && WhatsAppScreen(root).isOwnStatusList()
        OwnStatusObservation.summarize(provider, Build.VERSION.SDK_INT, nodes, complete, recognized)
    } catch (_: Exception) {
        JSONObject().put("contract_version", 1).put("snapshot_complete", false)
            .put("reason", "NATIVE_STRUCTURE_UNAVAILABLE").put("top_verified", false)
            .put("stable_media_identity_verified", false).put("publication_proof", false)
    }
}
