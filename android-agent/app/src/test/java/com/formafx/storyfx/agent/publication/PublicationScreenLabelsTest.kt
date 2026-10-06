package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PublicationScreenLabelsTest {
    @Test fun acceptsProviderTextAndAccessibilityDescriptions() {
        for (label in listOf("Updates", "Actus", "Mises à jour")) {
            assertTrue(PublicationScreenLabels.updates(label, ""))
            assertTrue(PublicationScreenLabels.updates("", label))
        }
        for (label in listOf("My status", "Mon statut")) {
            assertTrue(PublicationScreenLabels.own(label, ""))
            assertTrue(PublicationScreenLabels.own("", label))
        }
    }
    @Test fun refusesOtherRecipientsAndApproximateLabels() {
        for (label in listOf("Validation technique", "My status contact", "Status (Contacts)", "")) {
            assertFalse(PublicationScreenLabels.own(label, label))
        }
        assertFalse(PublicationScreenLabels.updates("Updates from Validation technique", ""))
        assertFalse(PublicationScreenLabels.updates("", ""))
    }
}
