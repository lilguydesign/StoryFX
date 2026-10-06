package com.formafx.storyfx.agent.publication

import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.Rect

/** Screen contents are inspected in memory, never logged or sent to the server. */
class WhatsAppScreen(root: AccessibilityNodeInfo?) {
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
    private fun clickableParent(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var target: AccessibilityNodeInfo? = node
        repeat(5) {
            if (target?.isClickable == true) return target
            target = target?.parent
        }
        return null
    }
    private fun updateTargets() = if (!correctPackage) emptyList() else nodes.filter {
        it.isVisibleToUser && PublicationScreenLabels.updates(text(it), description(it)) &&
            WhatsAppHomeShape.navigation(top(it), bounds.height())
    }.mapNotNull(::clickableParent).distinct()
    private fun unique(predicate: (AccessibilityNodeInfo) -> Boolean): AccessibilityNodeInfo {
        check(correctPackage)
        val found = nodes.filter { it.isVisibleToUser && predicate(it) }
        check(found.size == 1)
        return found.single()
    }
    private fun click(node: AccessibilityNodeInfo) {
        var target: AccessibilityNodeInfo? = node
        repeat(5) {
            if (target?.isClickable == true) {
                check(target!!.performAction(AccessibilityNodeInfo.ACTION_CLICK)); return
            }
            target = target?.parent
        }
        error("NO_CLICK_TARGET")
    }
    fun updates() { val targets = updateTargets(); check(targets.size == 1); click(targets.single()) }
    fun hasUpdates() = updateTargets().size == 1
    fun hasNoOwnStatus(): Boolean {
        if (!correctPackage) return false
        val visible = nodes.filter { it.isVisibleToUser }
        return WhatsAppHomeShape.empty(
            WhatsAppHomeShape.portrait(bounds.width(), bounds.height()),
            visible.any { PublicationScreenLabels.updates(text(it), description(it)) &&
                WhatsAppHomeShape.header(top(it), bounds.height()) },
            visible.any { text(it) in setOf("Status", "Statut", "Statuts") &&
                WhatsAppHomeShape.section(top(it), bounds.height()) },
            visible.any { PublicationScreenLabels.emptyOwn(text(it), description(it)) &&
                WhatsAppHomeShape.ownTile(position(it).centerX() - bounds.left, top(it), bounds.width(), bounds.height()) },
            visible.any(::own),
            visible.any { it.viewIdResourceName == "${PublicationPolicy.provider}:id/send" })
    }
    fun isOwnStatusList() = correctPackage && !hasUpdates() && nodes.count { it.isVisibleToUser && own(it) } == 1 &&
        nodes.none { it.isVisibleToUser && it.viewIdResourceName == "${PublicationPolicy.provider}:id/send" } &&
        nodes.any { it.isVisibleToUser && Regex("\\d+ (views?|vues?)", RegexOption.IGNORE_CASE).matches(text(it)) }
    fun ownStatus() = click(unique { own(it) })
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
