package com.formafx.storyfx.agent.publication

import org.json.JSONObject

/** A fresh visible row-zero witness, never a provider total or a stable media identity. */
object SequentialBaseline {
    fun read(value: JSONObject, minimumAged: Int, emptyOwnHome: Boolean): SequentialPublication.Baseline? {
        require(minimumAged in 0..9)
        if (minimumAged == 0 && emptyOwnHome) return SequentialPublication.Baseline(0)
        if (!value.optBoolean("provider_window") || !value.optBoolean("snapshot_complete") ||
            !value.optBoolean("own_list_recognized") || value.optBoolean("player_present", true) ||
            value.optBoolean("send_control_present", true) || value.optInt("list_container_count", -1) != 1 ||
            value.optInt("status_row_zero_candidates", -1) != 1 || value.optString("top_candidate") != "status_row_zero" ||
            value.optInt("pending_or_error_nodes", -1) != 0 || value.optInt("fresh_stamp_nodes", -1) != 0 ||
            value.optInt("complete_rows_unknown_age", -1) != 0) return null
        val aged = value.optInt("complete_rows_known_aged", -1)
        return if (aged >= maxOf(1, minimumAged)) SequentialPublication.Baseline(aged) else null
    }
}
