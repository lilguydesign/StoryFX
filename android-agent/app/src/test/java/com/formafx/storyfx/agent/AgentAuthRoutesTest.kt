package com.formafx.storyfx.agent

import org.junit.Assert.*
import org.junit.Test
import java.util.UUID

class AgentAuthRoutesTest {
    private val state = "S".repeat(43)
    private val ticket = "synthetic_ticket_validation"
    private val requestId = UUID.randomUUID().toString()

    @Test fun proofMatchesRfc7636Vector() {
        val pending = PendingAgentAuth(AgentAuthRoutes.publicServer, UUID.randomUUID().toString(),
            state, "N".repeat(43), "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk", 1L)
        assertEquals("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", pending.challenge())
    }

    @Test fun proofUsesIndependentRandomValuesAndRoundTrips() {
        val pending = AgentAuthProof.create(AgentAuthRoutes.publicServer, UUID.randomUUID().toString(), 1L)
        assertEquals(43, pending.state.length); assertEquals(43, pending.deviceNonce.length)
        assertEquals(86, pending.verifier.length); assertEquals(43, pending.challenge().length)
        assertNotEquals(pending.state, pending.deviceNonce)
        assertEquals(pending.verifier, PendingAgentAuth.fromJson(pending.toJson()).verifier)
        assertFalse(pending.toString().contains(pending.verifier))
    }

    @Test fun callbackAcceptsOnlyTicketAndState() {
        val result = AgentAuthRoutes.parseCallback("${AgentAuthRoutes.callback}?ticket=$ticket&state=$state")
        assertEquals(ticket, result.ticket); assertEquals(state, result.state)
    }

    @Test fun callbackRejectsAmbiguousOrForeignUrls() {
        val query = "?ticket=$ticket&state=$state"
        listOf("https://story.formafx.com/agent/callback$query", "storyfx-android://other/callback$query",
            "storyfx-android://auth/callback/extra$query", "${AgentAuthRoutes.callback}$query#extra",
            "${AgentAuthRoutes.callback}$query&ticket=$ticket", "${AgentAuthRoutes.callback}$query&token=synthetic")
            .forEach { rejects { AgentAuthRoutes.parseCallback(it) } }
    }

    @Test fun connectUrlRejectsOtherOriginsAndSensitiveQueries() {
        val base = AgentAuthRoutes.publicServer
        assertEquals("$base/agent/connect?request_id=$requestId",
            AgentAuthRoutes.validateConnectUrl("$base/agent/connect?request_id=$requestId", base, false))
        listOf("http://story.formafx.com/agent/connect?request_id=$requestId",
            "https://unrelated.invalid/agent/connect?request_id=$requestId",
            "$base/agent/connect?request_id=$requestId&token=synthetic",
            "$base/agent/connect?request_id=$requestId&request_id=$requestId",
            "$base/agent/connect/extra?request_id=$requestId")
            .forEach { rejects { AgentAuthRoutes.validateConnectUrl(it, base, false) } }
    }

    @Test fun stateComparisonRequiresExactMatch() {
        assertTrue(AgentAuthProof.stateMatches(state, state))
        assertFalse(AgentAuthProof.stateMatches(state, state.lowercase()))
        assertFalse(AgentAuthProof.stateMatches(state, state + "S"))
    }

    private fun rejects(action: () -> Any) {
        try { action(); fail("Unsafe auth URL accepted") } catch (_: AgentAuthException) { }
    }
}
