package com.formafx.storyfx.agent.publication

import android.view.accessibility.AccessibilityNodeInfo

/** Screen contents are inspected in memory, never logged or sent to the server. */
class WhatsAppScreen(root: AccessibilityNodeInfo?) {
    private val nodes = mutableListOf<AccessibilityNodeInfo>()
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
    private fun own(node: AccessibilityNodeInfo) = text(node) in setOf("My status", "Mon statut")
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
    fun updates() = click(unique { text(it) in setOf("Updates", "Actus", "Mises à jour") })
    fun ownStatus() = click(unique { own(it) })
    fun selectOwnStatus() = click(unique {
        it.viewIdResourceName == "${PublicationPolicy.provider}:id/contactpicker_row_name" && own(it)
    })
    fun recentCount(): Int {
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
