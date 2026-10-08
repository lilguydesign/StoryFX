package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class OwnStatusObservationTest {
    private fun fixture(): MutableList<OwnStatusObservation.Node> = mutableListOf(
        OwnStatusObservation.Node(own = true),
        OwnStatusObservation.Node(parent = 0, list = true, scrollable = true, forward = true))

    private fun row(nodes: MutableList<OwnStatusObservation.Node>, time: OwnStatusObservation.TimeClass,
                    index: Int? = null, pending: Boolean = false, unique: Boolean = false) {
        val parent = nodes.size
        nodes.add(OwnStatusObservation.Node(parent = 1, rowIndex = index, uniqueIdPresent = unique))
        nodes.add(OwnStatusObservation.Node(parent = parent, date = true, time = time))
        nodes.add(OwnStatusObservation.Node(parent = parent, views = true))
        if (pending) nodes.add(OwnStatusObservation.Node(parent = parent, pending = true))
    }

    @Test fun visibleCeilingOldRowsAndPendingRemainSeparateWithoutConfirming() {
        val nodes = fixture()
        repeat(8) { row(nodes, OwnStatusObservation.TimeClass.JUST_NOW) }
        row(nodes, OwnStatusObservation.TimeClass.MINUTES)
        row(nodes, OwnStatusObservation.TimeClass.JUST_NOW, pending = true)
        val result = OwnStatusObservation.summarize(true, 35, nodes, true, true)
        assertEquals(10, result.getInt("date_nodes"))
        assertEquals(9, result.getInt("fresh_stamp_nodes"))
        assertEquals(9, result.getInt("complete_rows_all_ages"))
        assertEquals(8, result.getInt("complete_rows_fresh"))
        assertEquals(1, result.getInt("complete_rows_known_aged"))
        assertEquals(1, result.getInt("pending_or_error_nodes"))
        assertEquals("backward_not_advertised", result.getString("top_candidate"))
        assertFalse(result.getBoolean("top_verified"))
        assertFalse(result.getBoolean("publication_proof"))
    }

    @Test fun unavailableIndicesNeverCountOrSelectTheTimestampAsARow() {
        val nodes = fixture()
        nodes[1] = nodes[1].copy(collectionRows = -1, collectionColumns = -1)
        row(nodes, OwnStatusObservation.TimeClass.JUST_NOW, index = -1)
        nodes[3] = nodes[3].copy(rowIndex = -1)
        val result = OwnStatusObservation.summarize(true, 35, nodes, true, true)
        assertEquals(1, result.getInt("complete_rows_fresh"))
        assertEquals(0, result.getInt("nodes_with_row_index"))
        assertEquals(0, result.getInt("status_rows_with_index"))
        assertTrue(result.isNull("provider_collection_total"))
        assertTrue(result.getJSONArray("containers").getJSONObject(0).isNull("rows"))
    }

    @Test fun zeroHeaderAndPlayerDoNotAttestListBeginning() {
        val nodes = fixture()
        nodes[0] = nodes[0].copy(rowIndex = 0)
        nodes[1] = nodes[1].copy(backward = true)
        row(nodes, OwnStatusObservation.TimeClass.MINUTES, index = 4)
        var result = OwnStatusObservation.summarize(true, 35, nodes, true, true)
        assertEquals("unknown", result.getString("top_candidate"))
        assertEquals(0, result.getInt("status_row_zero_candidates"))
        nodes[2] = nodes[2].copy(rowIndex = 0)
        result = OwnStatusObservation.summarize(true, 35, nodes, true, true)
        assertEquals("status_row_zero", result.getString("top_candidate"))
        nodes.add(OwnStatusObservation.Node(player = true))
        result = OwnStatusObservation.summarize(true, 35, nodes, true, true)
        assertEquals("unknown", result.getString("top_candidate"))
        assertTrue(result.getBoolean("player_present"))
    }

    @Test fun duplicateIndicesAndUniqueIdsArePresenceNotMediaIdentity() {
        val nodes = fixture()
        repeat(2) { row(nodes, OwnStatusObservation.TimeClass.JUST_NOW, index = 0, unique = true) }
        val result = OwnStatusObservation.summarize(true, 35, nodes, true, true)
        assertEquals(2, result.getInt("status_rows_with_index"))
        assertEquals(1, result.getInt("distinct_status_row_indices"))
        assertEquals(2, result.getInt("status_rows_with_unique_id"))
        assertEquals("unknown", result.getString("top_candidate"))
        assertFalse(result.getBoolean("stable_media_identity_verified"))
        assertFalse(result.getBoolean("publication_proof"))
    }

    @Test fun minApiNeverReadsUniqueIdAndPrivateLabelsBecomeClosedClasses() {
        for (sdk in listOf(26, 32)) assertFalse(OwnStatusObservation.uniqueIdPresent(sdk) { error("API33 only") })
        assertFalse(OwnStatusObservation.uniqueIdPresent(33) { null })
        assertTrue(OwnStatusObservation.uniqueIdPresent(35) { "PRIVATE_NODE_ID" })
        val nodes = fixture()
        row(nodes, OwnStatusObservation.timeClass("PRIVATE_MEDIA_LABEL"), unique = true)
        val result = OwnStatusObservation.summarize(true, 26, nodes, true, true)
        assertEquals(0, result.getInt("nodes_with_unique_id"))
        assertEquals(1, result.getInt("complete_rows_unknown_age"))
        assertFalse(result.toString().contains("PRIVATE"))
        assertEquals(OwnStatusObservation.TimeClass.UNKNOWN, OwnStatusObservation.timeClass("0 minutes ago"))
        assertEquals(OwnStatusObservation.TimeClass.CLOCK, OwnStatusObservation.timeClass("13:40"))
    }

    @Test fun incompleteOrWrongProviderSnapshotsCannotSupplyTopCandidateOrTotals() {
        val nodes = fixture()
        nodes[1] = nodes[1].copy(collectionRows = 58, collectionColumns = 1)
        row(nodes, OwnStatusObservation.TimeClass.MINUTES, index = 0)
        val incomplete = OwnStatusObservation.summarize(true, 35, nodes, false, true)
        assertEquals("unknown", incomplete.getString("top_candidate"))
        assertTrue(incomplete.isNull("provider_collection_total"))
        val result = OwnStatusObservation.summarize(false, 35, nodes, true, true)
        assertEquals(0, result.getInt("provider_nodes"))
        assertEquals(0, result.getInt("complete_rows_all_ages"))
        assertFalse(result.getBoolean("own_list_recognized"))
        assertTrue(result.isNull("provider_collection_total"))
    }
}
