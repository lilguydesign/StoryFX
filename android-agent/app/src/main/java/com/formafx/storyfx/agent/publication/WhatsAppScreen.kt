package com.formafx.storyfx.agent.publication

import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.Rect
import org.json.JSONObject

/** Screen contents are inspected in memory, never logged or sent to the server. */
class WhatsAppScreen(root: AccessibilityNodeInfo?, private val tap: ((Int, Int) -> Boolean)? = null) {
    private val nodes = mutableListOf<AccessibilityNodeInfo>()
    private val bounds = Rect().also { root?.getBoundsInScreen(it) }
    private fun position(node: AccessibilityNodeInfo) = Rect().also { node.getBoundsInScreen(it) }
    private fun top(node: AccessibilityNodeInfo) = position(node).top - bounds.top
    val correctPackage = root?.packageName?.toString() == PublicationPolicy.provider
    init {
        fun walk(node: AccessibilityNodeInfo) {
            if (nodes.size >= 2500) error("SCREEN_TOO_LARGE")
            nodes.add(node)
            for (index in 0 until node.childCount) node.getChild(index)?.let { walk(it) }
        }
        if (correctPackage && root != null) walk(root)
    }
    private fun text(node: AccessibilityNodeInfo) = node.text?.toString().orEmpty()
    private fun description(node: AccessibilityNodeInfo) = node.contentDescription?.toString().orEmpty()
    private fun own(node: AccessibilityNodeInfo) = PublicationScreenLabels.own(text(node), description(node))
    private fun acceptsClick(node: AccessibilityNodeInfo, navigation: Boolean): Boolean {
        val area = position(node)
        return node.packageName?.toString() == PublicationPolicy.provider &&
            (node.isClickable || node.actionList.any { it.id == AccessibilityNodeInfo.ACTION_CLICK }) &&
            ProviderClickShape.accepts(area.width(), area.height(), bounds.width(), bounds.height(), navigation)
    }
    private fun clickableParent(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var target: AccessibilityNodeInfo? = node
        repeat(12) {
            if (target != null && acceptsClick(target!!, true)) return target
            target = target?.parent
        }
        return null
    }
    private fun acceptsTap(node: AccessibilityNodeInfo, navigation: Boolean): Boolean {
        val area = position(node)
        return node.isVisibleToUser && node.packageName?.toString() == PublicationPolicy.provider &&
            bounds.contains(area) && ProviderClickShape.accepts(area.width(), area.height(),
                bounds.width(), bounds.height(), navigation)
    }
    private fun updateTargets(): List<AccessibilityNodeInfo> {
        if (!correctPackage) return emptyList()
        val visible = nodes.filter { it.isVisibleToUser && WhatsAppHomeShape.navigation(top(it), bounds.height()) }
        val textTargets = visible.filter { PublicationScreenLabels.updates(text(it), "") }
        val targets = textTargets.ifEmpty { visible.filter { PublicationScreenLabels.updates("", description(it)) } }
        return targets.mapNotNull { clickableParent(it) ?: it.takeIf { node -> acceptsTap(node, true) } }.distinct()
    }
    private fun unique(predicate: (AccessibilityNodeInfo) -> Boolean): AccessibilityNodeInfo {
        check(correctPackage)
        val found = nodes.filter { it.isVisibleToUser && predicate(it) }
        check(found.size == 1)
        return found.single()
    }
    private fun click(node: AccessibilityNodeInfo) {
        var target: AccessibilityNodeInfo? = node
        repeat(12) {
            if (target != null && acceptsClick(target!!, false)) {
                check(target!!.performAction(AccessibilityNodeInfo.ACTION_CLICK)); return
            }
            target = target?.parent
        }
        // No second gesture after an attempted ACTION_CLICK: its outcome could be uncertain.
        // Fallback is reserved for an exact unique label/id with no actionable ancestor.
        check(correctPackage && acceptsTap(node, false))
        val area = position(node)
        check(requireNotNull(tap)(area.centerX(), area.centerY()))
    }
    fun updates() { val targets = updateTargets(); check(targets.size == 1); click(targets.single()) }
    fun hasUpdates() = updateTargets().size == 1
    fun ownStatusReady(): Boolean {
        if (isOwnStatusList()) return true
        val evidence = homeEvidence()
        return correctPackage && evidence.getBoolean("portrait") && evidence.getBoolean("header") &&
            evidence.getBoolean("section") && !evidence.getBoolean("send_control") &&
            nodes.count { it.isVisibleToUser && own(it) } == 1
    }
    /** Closed structural flags only: no contact labels, captions or password contents. */
    fun homeEvidence(): JSONObject {
        val visible = nodes.filter { it.isVisibleToUser }
        return JSONObject().put("provider_window", correctPackage).put("provider_node_count", nodes.size)
            .put("picker_header", visible.any { text(it) in setOf("Send to…", "Send to...", "Envoyer à…", "Envoyer à...") })
            .put("picker_own_text_nodes", visible.count { PublicationScreenLabels.own(text(it), "") })
            .put("picker_own_named_rows", visible.count { own(it) && it.viewIdResourceName == "${PublicationPolicy.provider}:id/contactpicker_row_name" })
            .put("portrait", WhatsAppHomeShape.portrait(bounds.width(), bounds.height()))
            .put("root_width", bounds.width()).put("root_height", bounds.height())
            .put("header", visible.any { PublicationScreenLabels.updates(text(it), "") &&
                WhatsAppHomeShape.header(top(it), bounds.height()) })
            .put("section", visible.any { text(it) in setOf("Status", "Statut", "Statuts") &&
                WhatsAppHomeShape.section(top(it), bounds.height()) })
            .put("empty_tile_text", visible.any { PublicationScreenLabels.emptyOwn(text(it), "") &&
                WhatsAppHomeShape.ownTile(position(it).centerX() - bounds.left, top(it), bounds.width(), bounds.height()) })
            .put("own_status_text", visible.any { PublicationScreenLabels.own(text(it), "") })
            .put("own_avatar_description", visible.any { PublicationScreenLabels.own("", description(it)) })
            .put("send_control", visible.any { it.viewIdResourceName == "${PublicationPolicy.provider}:id/send" })
            .put("updates_navigation", hasUpdates()).put("updates_targets", updateTargets().size)
            .put("updates_text_nodes", visible.count { PublicationScreenLabels.updates(text(it), "") &&
                WhatsAppHomeShape.navigation(top(it), bounds.height()) })
            .put("own_label_all_nodes", nodes.count { own(it) })
            .put("own_list", isOwnStatusList()).put("own_list_total", statusCount() ?: JSONObject.NULL)
            .put("own_prefix_all_nodes", nodes.count { text(it).startsWith("My status") || description(it).startsWith("My status") })
            .put("own_list_containers", org.json.JSONArray(nodes.filter { it.isVisibleToUser && it.isScrollable }
                .map { JSONObject().put("recycler", it.className?.toString()?.endsWith("RecyclerView") == true)
                    .put("list", it.className?.toString()?.endsWith("ListView") == true)
                    .put("rows", it.collectionInfo?.rowCount ?: -1).put("columns", it.collectionInfo?.columnCount ?: -1) }))
    }
    fun hasNoOwnStatus(): Boolean {
        if (!correctPackage) return false
        val evidence = homeEvidence()
        // An empty own-avatar may still be described as My status. Only its exact
        // visible Add status text establishes an empty tile; an Add status button
        // description on an active tile or a send screen cannot provide this proof.
        return WhatsAppHomeShape.empty(evidence.getBoolean("portrait"), evidence.getBoolean("header"),
            evidence.getBoolean("section"), evidence.getBoolean("empty_tile_text"),
            evidence.getBoolean("own_status_text"), evidence.getBoolean("send_control"))
    }
    fun isOwnStatusList() = correctPackage && !hasUpdates() && nodes.count { it.isVisibleToUser && own(it) } == 1 &&
        nodes.none { it.isVisibleToUser && it.viewIdResourceName == "${PublicationPolicy.provider}:id/send" } &&
        nodes.any { it.isVisibleToUser && Regex("\\d+ (views?|vues?)", RegexOption.IGNORE_CASE).matches(text(it)) }
    fun ownStatus() = click(unique { own(it) })
    fun statusCount(): Int? {
        if (!isOwnStatusList()) return null
        return nodes.filter { it.isVisibleToUser && it.isScrollable &&
            (it.className?.toString()?.endsWith("RecyclerView") == true || it.className?.toString()?.endsWith("ListView") == true) }
            .mapNotNull { it.collectionInfo?.takeIf { info -> info.columnCount == 1 && info.rowCount in 0..600 }?.rowCount }
            .distinct().singleOrNull()
    }
    fun openOwnStatus() { if (!hasNoOwnStatus() && !isOwnStatusList()) ownStatus() }
    fun selectOwnStatus() = click(unique {
        it.viewIdResourceName == "${PublicationPolicy.provider}:id/contactpicker_row_name" && own(it)
    })
    fun recentCount(): Int {
        if (hasNoOwnStatus()) return 0
        unique { own(it) }
        return nodes.count { it.isVisibleToUser && text(it) in setOf("Just now", "À l’instant", "À l'instant") }
    }
    fun recentRows(): Set<Int>? {
        val recent = nodes.filter { it.isVisibleToUser && text(it) in setOf("Just now", "À l’instant", "À l'instant") }
        val rows = recent.map { node ->
            var parent: AccessibilityNodeInfo? = node
            var index: Int? = null
            repeat(6) {
                if (index == null) index = parent?.collectionItemInfo?.rowIndex?.takeIf { it >= 0 }
                parent = parent?.parent
            }
            index
        }
        return if (rows.any { it == null }) null else rows.filterNotNull().toSet()
    }
    fun scrollStatuses(): Boolean = unique {
        it.isScrollable && (it.className?.toString()?.endsWith("RecyclerView") == true ||
            it.className?.toString()?.endsWith("ListView") == true)
    }.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
    fun selectionIsOwnOnly(): Boolean = correctPackage && nodes.count {
        it.isVisibleToUser && text(it) in setOf("1 selected", "1 sélectionné", "1 sélectionnée")
    } == 1
    fun contactsPreview(): Boolean = correctPackage && nodes.count {
        it.isVisibleToUser && (text(it).contains("Status (Contacts)") || text(it).contains("Statut (Contacts)"))
    } == 1
    fun send() = click(unique { it.viewIdResourceName == "${PublicationPolicy.provider}:id/send" })
}
