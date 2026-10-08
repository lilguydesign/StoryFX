package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class OwnStatusListShapeTest {
    private fun node(id: String, type: String = "android.widget.TextView", visible: Boolean = true) =
        OwnStatusListShape.Node(type, "${PublicationPolicy.provider}:id/$id", visible)

    @Test fun observedOwnPlayerWithNameAndReadReceiptCounterIsNeverAList() {
        val player = listOf(node("name"), node("read_receipt_counter"),
            node("playback_progress", "android.widget.ProgressBar"),
            node("playback_pager", "androidx.viewpager.widget.ViewPager"))
        assertFalse(OwnStatusListShape.accepts(player))
        // Even a visible leftover list behind the player must not turn playback into list evidence.
        assertFalse(OwnStatusListShape.accepts(player + node("list", "android.widget.ListView")))
    }

    @Test fun realListDoesNotNeedCollectionRowCountOrScrollableFlagToBeRecognized() {
        val rows = listOf(node("name"), node("contact_photo", "android.widget.ImageView"),
            node("date_time"), node("views_count"))
        assertFalse(OwnStatusListShape.accepts(rows))
        for (type in listOf("android.widget.ListView", "androidx.recyclerview.widget.RecyclerView")) {
            assertTrue(OwnStatusListShape.accepts(rows + node("list", type)))
            assertFalse(OwnStatusListShape.accepts(rows + node("list", type, visible = false)))
        }
    }

    @Test fun eachObservedPlayerAnchorIndependentlyExcludesListClassification() {
        val list = listOf(node("list", "android.widget.ListView"), node("views_count"))
        for (id in listOf("playback_progress", "playback_pager")) {
            assertFalse(OwnStatusListShape.accepts(list + node(id)))
            assertTrue(OwnStatusListShape.accepts(list + node(id, visible = false)))
        }
    }
}
