package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class OwnStatusTargetsTest {
    private data class Node(val text: String = "", val description: String = "", val control: Int = 0)
    private fun resolve(vararg nodes: Node) = OwnStatusTargets.resolve(nodes.toList(), Node::text, Node::description) { a, b ->
        a.control != 0 && a.control == b.control
    }

    @Test fun visibleLabelTakesPriorityOverItsAvatarDescription() {
        val title = Node("My status", control = 1)
        assertEquals(listOf(title), resolve(title, Node(description = "My status", control = 1)))
    }

    @Test fun multipleLabelsOrAvatarsRemainAmbiguous() {
        assertEquals(2, resolve(Node("My status"), Node("Mon statut")).size)
        assertEquals(2, resolve(Node(description = "My status"), Node(description = "Mon statut")).size)
    }

    @Test fun arbitraryContactsAreNotOwnStatusTargets() {
        assertTrue(resolve(Node("My status contact"), Node("Validation technique")).isEmpty())
    }

    @Test fun unrelatedContactWithSameExactNameDoesNotSuppressTheOwnAvatar() {
        assertEquals(2, resolve(Node("My status", control = 2), Node(description = "My status", control = 1)).size)
        assertEquals(2, resolve(Node("My status"), Node(description = "My status")).size)
    }
}
