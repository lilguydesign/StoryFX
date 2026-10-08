package com.formafx.storyfx.agent.publication

/** A views counter also exists in the player; it is not a list-container anchor. */
object OwnStatusListShape {
    data class Node(val className: String, val resourceId: String, val visible: Boolean = true)
    private val playbackIds = setOf("playback_progress", "playback_pager")
        .map { "${PublicationPolicy.provider}:id/$it" }.toSet()

    fun accepts(nodes: List<Node>): Boolean {
        val visible = nodes.filter { it.visible }
        return visible.none { it.resourceId in playbackIds } && visible.any {
            it.className.endsWith("ListView") || it.className.endsWith("RecyclerView")
        }
    }
}
