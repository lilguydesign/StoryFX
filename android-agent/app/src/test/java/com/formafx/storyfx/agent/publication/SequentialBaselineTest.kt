package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class SequentialBaselineTest {
    private fun ready() = JSONObject().put("provider_window", true).put("snapshot_complete", true)
        .put("own_list_recognized", true).put("player_present", false).put("send_control_present", false)
        .put("list_container_count", 1).put("status_row_zero_candidates", 1).put("top_candidate", "status_row_zero")
        .put("pending_or_error_nodes", 0).put("fresh_stamp_nodes", 0)
        .put("complete_rows_unknown_age", 0).put("complete_rows_known_aged", 10)

    @Test fun emptyHomeOnlyAllowedBeforeTheFirstSlice() {
        assertEquals(0, SequentialBaseline.read(JSONObject(), 0, true)?.agedRows)
        assertNull(SequentialBaseline.read(JSONObject(), 9, true))
    }
    @Test fun observedRowZeroAndAgedRowsAreRequired() {
        assertEquals(10, SequentialBaseline.read(ready(), 9, false)?.agedRows)
        for (field in listOf("status_row_zero_candidates", "list_container_count")) {
            assertNull(SequentialBaseline.read(ready().put(field, 2), 9, false))
        }
        assertNull(SequentialBaseline.read(ready().put("complete_rows_known_aged", 8), 9, false))
        assertNull(SequentialBaseline.read(ready().put("top_candidate", "backward_not_advertised"), 9, false))
    }
    @Test fun freshPendingUnknownAndIncompleteSnapshotsRefuse() {
        for (field in listOf("fresh_stamp_nodes", "pending_or_error_nodes", "complete_rows_unknown_age")) {
            assertNull(SequentialBaseline.read(ready().put(field, 1), 9, false))
        }
        assertNull(SequentialBaseline.read(ready().put("snapshot_complete", false), 9, false))
        assertNull(SequentialBaseline.read(ready().put("player_present", true), 9, false))
    }
}
