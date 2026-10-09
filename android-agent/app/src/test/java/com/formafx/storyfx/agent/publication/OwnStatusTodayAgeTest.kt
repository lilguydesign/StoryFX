package com.formafx.storyfx.agent.publication

import java.time.LocalTime
import org.junit.Assert.*
import org.junit.Test

class OwnStatusTodayAgeTest {
    @Test fun physicallyObservedEnglishTodayBecomesAgedOnlyAfterTwoMinutes() {
        assertTrue(OwnStatusTodayAge.isAged("Today, 5:58 AM", LocalTime.of(7, 22)))
        assertFalse(OwnStatusTodayAge.isAged("Today, 5:58 AM", LocalTime.of(5, 59, 59)))
        assertTrue(OwnStatusTodayAge.isAged("Today, 5:58 AM", LocalTime.of(6, 0)))
        assertEquals(OwnStatusObservation.TimeClass.TODAY_AGED,
            OwnStatusObservation.timeClass("Today, 5:58 AM", LocalTime.of(7, 22)))
    }

    @Test fun midnightNoonAndAfternoonAreNotConfused() {
        assertTrue(OwnStatusTodayAge.isAged("Today, 12:00 AM", LocalTime.of(0, 2)))
        assertFalse(OwnStatusTodayAge.isAged("Today, 12:00 PM", LocalTime.of(11, 59)))
        assertTrue(OwnStatusTodayAge.isAged("Today, 12:00 PM", LocalTime.of(12, 2)))
        assertFalse(OwnStatusTodayAge.isAged("Today, 5:58 PM", LocalTime.of(7, 22)))
        assertTrue(OwnStatusTodayAge.isAged("Today, 5:58 PM", LocalTime.of(18, 0)))
    }

    @Test fun frenchAndTwentyFourHourLabelsAllowUnicodeSpaces() {
        for (label in listOf("Aujourd'hui, 05:58", "Aujourd’hui, 05:58", "Today, 05:58",
                "Today,\u00a05:58\u202fAM")) {
            assertTrue(label, OwnStatusTodayAge.isAged(label, LocalTime.of(7, 22)))
        }
    }

    @Test fun futureAmbiguousInvalidOrUnrelatedLabelsRemainUnknown() {
        for (label in listOf("Today, 23:59", "Today, 25:00", "Today, 5:60 AM", "Today, 0:58 AM",
                "Today, 13:58 PM", "Today, 05:58 AM trailing", "05:58", "5:58 AM",
                "Yesterday, 5:58 AM", "Today", "Validation technique", "Today, 5:58 am")) {
            assertFalse(label, OwnStatusTodayAge.isAged(label, LocalTime.of(7, 22)))
        }
        assertEquals(OwnStatusObservation.TimeClass.UNKNOWN,
            OwnStatusObservation.timeClass("Today, 5:58 AM", LocalTime.of(5, 59)))
    }

    @Test fun knownAgedClassificationStillDoesNotAttestPublicationOrIdentity() {
        val nodes = listOf(OwnStatusObservation.Node(list=true),
            OwnStatusObservation.Node(parent=0,rowIndex=0),
            OwnStatusObservation.Node(parent=1,date=true,time=OwnStatusObservation.timeClass(
                "Today, 5:58 AM",LocalTime.of(7,22))), OwnStatusObservation.Node(parent=1,views=true))
        val evidence = OwnStatusObservation.summarize(true,35,nodes,true,true)
        assertEquals(1,evidence.getInt("complete_rows_known_aged"))
        assertEquals(0,evidence.getInt("complete_rows_unknown_age"))
        assertFalse(evidence.getBoolean("publication_proof"))
        assertFalse(evidence.getBoolean("stable_media_identity_verified"))
        assertEquals(0,evidence.getInt("complete_rows_fresh"))
    }
}
