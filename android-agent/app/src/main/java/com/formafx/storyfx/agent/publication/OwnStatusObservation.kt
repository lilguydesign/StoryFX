package com.formafx.storyfx.agent.publication

import org.json.JSONArray
import org.json.JSONObject

/** Closed diagnostic facts only. A position or missing action never proves media identity. */
object OwnStatusObservation {
    enum class TimeClass { JUST_NOW, MINUTES, HOURS, YESTERDAY, CLOCK, UNKNOWN }
    data class Node(
        val parent: Int? = null, val visible: Boolean = true, val list: Boolean = false,
        val scrollable: Boolean = false, val backward: Boolean = false, val forward: Boolean = false,
        val date: Boolean = false, val time: TimeClass = TimeClass.UNKNOWN, val views: Boolean = false,
        val pending: Boolean = false, val rowIndex: Int? = null, val collectionRows: Int? = null,
        val collectionColumns: Int? = null, val uniqueIdPresent: Boolean = false,
        val own: Boolean = false, val player: Boolean = false, val send: Boolean = false
    )
    private data class Row(val node: Int, val container: Int?, val time: TimeClass, val complete: Boolean)

    fun timeClass(text: String): TimeClass = when {
        text in setOf("Just now", "À l’instant", "À l'instant") -> TimeClass.JUST_NOW
        Regex("[1-9]\\d* minutes? ago|[Ii]l y a [1-9]\\d* min(?:ute)?s?").matches(text) -> TimeClass.MINUTES
        Regex("[1-9]\\d* hours? ago|[Ii]l y a [1-9]\\d* heures?").matches(text) -> TimeClass.HOURS
        Regex("Yesterday(?:,? .*)?|Hier(?:,? .*)?").matches(text) -> TimeClass.YESTERDAY
        Regex("\\d{1,2}:\\d{2}(?: [AP]M)?").matches(text) -> TimeClass.CLOCK
        else -> TimeClass.UNKNOWN
    }

    fun uniqueIdPresent(sdk: Int, read: () -> String?): Boolean = sdk >= 33 && !read().isNullOrEmpty()
    private fun known(value: Int?) = value?.takeIf { it >= 0 }

    fun summarize(provider: Boolean, sdk: Int, source: List<Node>, complete: Boolean,
                  ownListRecognized: Boolean): JSONObject {
        require(source.size <= 2500 && source.withIndex().all { (index, node) ->
            node.parent == null || node.parent in 0 until index
        })
        val nodes = if (provider) source else emptyList()
        val children = List(nodes.size) { mutableListOf<Int>() }
        nodes.forEachIndexed { index, node -> node.parent?.let { children[it].add(index) } }
        val visible = nodes.indices.filter { nodes[it].visible }
        val lists = visible.filter { nodes[it].list }
        fun ancestors(start: Int) = generateSequence(start) { nodes[it].parent }
        fun subtree(start: Int): Pair<List<Int>, Boolean> {
            val result = mutableListOf<Int>()
            val stack = java.util.ArrayDeque<Int>().apply { add(start) }
            var visited = 0
            while (stack.isNotEmpty() && visited < 500) {
                val current = stack.removeLast(); visited++
                if (nodes[current].visible) result.add(current)
                children[current].forEach(stack::add)
            }
            return result to stack.isEmpty()
        }
        val rows = visible.filter { nodes[it].date }.mapNotNull { stamp ->
            val candidates = ancestors(stamp).take(6).map { index -> index to subtree(index) }.toList()
            val candidate = candidates.firstOrNull { known(nodes[it.first].rowIndex) != null }
                ?: candidates.firstOrNull { (_, branch) -> branch.first.any { nodes[it].views } }
                ?: return@mapNotNull null
            val (index, branch) = candidate
            val dates = branch.first.filter { nodes[it].date }
            val time = dates.singleOrNull()?.let { nodes[it].time } ?: TimeClass.UNKNOWN
            Row(index, ancestors(index).drop(1).firstOrNull { it in lists }, time,
                branch.second && dates.size == 1 && branch.first.count { nodes[it].views } == 1 &&
                    branch.first.none { nodes[it].pending })
        }.distinctBy { it.node }
        val completed = rows.filter { it.complete && it.container != null }
        val player = visible.any { nodes[it].player }
        val send = visible.any { nodes[it].send }
        val list = lists.singleOrNull()
        val zeroRows = completed.count { it.container == list && known(nodes[it.node].rowIndex) == 0 }
        val top = when {
            !complete || !ownListRecognized || player || send || list == null -> "unknown"
            zeroRows > 1 -> "unknown"
            zeroRows == 1 -> "status_row_zero"
            nodes[list].scrollable && !nodes[list].backward -> "backward_not_advertised"
            else -> "unknown"
        }
        val rowIndices = rows.mapNotNull { known(nodes[it.node].rowIndex) }
        val knownAges = setOf(TimeClass.MINUTES, TimeClass.HOURS, TimeClass.YESTERDAY)
        val total = list?.let { nodes[it] }?.takeIf {
            complete && ownListRecognized && !player && !send && known(it.collectionColumns) == 1
        }
            ?.let { known(it.collectionRows) }
        return JSONObject().put("contract_version", 1).put("provider_window", provider)
            .put("snapshot_complete", complete).put("provider_nodes", nodes.size)
            .put("visible_nodes", visible.size).put("own_label_nodes", visible.count { nodes[it].own })
            .put("own_list_recognized", ownListRecognized && provider)
            .put("player_present", player).put("send_control_present", send)
            .put("list_container_count", lists.size).put("provider_collection_total", total ?: JSONObject.NULL)
            .put("containers", JSONArray(lists.map { index -> nodes[index].let {
                JSONObject().put("rows", known(it.collectionRows) ?: JSONObject.NULL)
                    .put("columns", known(it.collectionColumns) ?: JSONObject.NULL)
                    .put("scrollable", it.scrollable).put("backward_advertised", it.backward)
                    .put("forward_advertised", it.forward)
            } }))
            .put("date_nodes", visible.count { nodes[it].date })
            .put("fresh_stamp_nodes", visible.count { nodes[it].time == TimeClass.JUST_NOW })
            .put("time_classes", JSONObject().apply { TimeClass.entries.forEach { category ->
                put(category.name.lowercase(), visible.count { nodes[it].date && nodes[it].time == category })
            } })
            .put("view_indicator_nodes", visible.count { nodes[it].views })
            .put("pending_or_error_nodes", visible.count { nodes[it].pending })
            .put("complete_rows_all_ages", completed.size)
            .put("complete_rows_fresh", completed.count { it.time == TimeClass.JUST_NOW })
            .put("complete_rows_known_aged", completed.count { it.time in knownAges })
            .put("complete_rows_unknown_age", completed.count { it.time in setOf(TimeClass.CLOCK, TimeClass.UNKNOWN) })
            .put("nodes_with_row_index", visible.count { known(nodes[it].rowIndex) != null })
            .put("status_rows_with_index", rowIndices.size)
            .put("distinct_status_row_indices", rowIndices.distinct().size).put("status_row_zero_candidates", zeroRows)
            .put("unique_id_api_available", sdk >= 33)
            .put("nodes_with_unique_id", visible.count { sdk >= 33 && nodes[it].uniqueIdPresent })
            .put("status_rows_with_unique_id", rows.count { sdk >= 33 && nodes[it.node].uniqueIdPresent })
            .put("top_candidate", top).put("top_verified", false)
            .put("stable_media_identity_verified", false).put("publication_proof", false)
    }
}
