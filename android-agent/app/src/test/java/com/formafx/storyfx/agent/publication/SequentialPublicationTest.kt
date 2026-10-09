package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class SequentialPublicationTest {
    private class Trial {
        var clock = 1000L
        val sends = mutableListOf<List<Int>>()
        val records = mutableListOf<JSONObject>()
        var complete = false
        fun runner(deadline: Long = 780000) = SequentialPublication<Int>({ clock }, deadline, {}, { clock += it })
        fun baseline(minimum: Int): SequentialPublication.Baseline { clock += 5; return SequentialPublication.Baseline(maxOf(1, minimum)) }
        fun send(media: List<Int>) { sends.add(media); clock += 10 }
        fun verify(count: Int): PublicationVerification.Evidence { clock += 10; return PublicationVerification.Evidence(count, "recent_visible") }
        fun persist(proof: JSONObject, done: Boolean) { records.add(JSONObject(proof.toString())); complete = done }
    }

    @Test fun slicesAreDisjointOrderedAndEntirelyProven() {
        val t = Trial()
        val proof = t.runner().execute((1..11).toList(), listOf(9, 2), t::baseline, t::send, t::verify, t::persist)
        assertEquals(listOf((1..9).toList(), listOf(10, 11)), t.sends)
        assertEquals(listOf(9, 2), (0 until 2).map(proof.getJSONArray("verified_counts")::getInt))
        assertTrue(t.complete)
        assertEquals(0, t.records.first().getJSONArray("baseline_elapsed_ms").length())
        assertEquals(1, t.records[1].getJSONArray("baseline_elapsed_ms").length())
        assertEquals(0, t.records[1].getJSONArray("verified_counts").length())
        assertTrue(proof.getJSONArray("baseline_elapsed_ms").getLong(1) > proof.getJSONArray("verified_elapsed_ms").getLong(0))
    }

    @Test fun introIsFirstAndQuotaIsNeverReduced() {
        assertEquals(listOf(1, 9, 2), SequentialPublication.sizes(listOf(1, 11)))
        assertEquals(listOf(9, 9, 9, 3), SequentialPublication.sizes(listOf(30)))
        assertEquals(listOf(1, 9, 9, 9, 2), SequentialPublication.sizes(listOf(1, 29)))
    }

    @Test fun uncertainSecondSliceCannotBeReentered() {
        val t = Trial(); val r = t.runner()
        val send: (List<Int>) -> Unit = { t.send(it); if (t.sends.size == 2) error("LOST_RESPONSE") }
        assertThrows(IllegalStateException::class.java) {
            r.execute((1..11).toList(), listOf(9, 2), t::baseline, send, t::verify, t::persist)
        }
        assertFalse(t.complete)
        assertEquals(1, t.records.last().getJSONArray("verified_counts").length())
        assertThrows(IllegalStateException::class.java) {
            r.execute((1..11).toList(), listOf(9, 2), t::baseline, send, t::verify, t::persist)
        }
        assertEquals(2, t.sends.size)
    }

    @Test fun failedPersistenceOrDuplicateMediaSendsNothing() {
        val t = Trial()
        assertThrows(IllegalStateException::class.java) {
            t.runner().execute((1..11).toList(), listOf(9, 2), t::baseline, t::send, t::verify) { _, _ -> error("STORE_FAILED") }
        }
        assertTrue(t.sends.isEmpty())
        assertThrows(IllegalArgumentException::class.java) {
            t.runner().execute(List(11) { 1 }, listOf(9, 2), t::baseline, t::send, t::verify, t::persist)
        }
        assertTrue(t.sends.isEmpty())
    }

    @Test fun missingBaselineExpiresWithoutSendingNextSlice() {
        val t = Trial()
        assertThrows(IllegalStateException::class.java) {
            t.runner(1100).execute((1..11).toList(), listOf(9, 2),
                { minimum -> if (minimum == 0) t.baseline(0) else null }, t::send, t::verify, t::persist)
        }
        assertEquals(1, t.sends.size)
        assertFalse(t.complete)
    }

    @Test fun partialViewNeverCompletesOrSendsNextSlice() {
        val t = Trial()
        assertThrows(IllegalStateException::class.java) {
            t.runner().execute((1..11).toList(), listOf(9, 2), t::baseline, t::send,
                { t.clock += 10; PublicationVerification.Evidence(8, "none") }, t::persist)
        }
        assertEquals(1, t.sends.size)
        assertFalse(t.complete)
    }
}
