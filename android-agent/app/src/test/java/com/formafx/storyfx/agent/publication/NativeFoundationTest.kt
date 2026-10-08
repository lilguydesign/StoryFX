package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class NativeFoundationTest {
    @Test fun migrationPreservesLegacyStopAndAnAssociationCannotTurnItOn() {
        val stopped = PublicationActivation.restore(null, false).withBinding(true)
        assertFalse(stopped.globalEnabled)
        assertTrue(stopped.whatsAppEnabled)
        assertFalse(stopped.withBinding(false).withBinding(true).globalEnabled)
        assertTrue(PublicationActivation.restore(null, true).globalEnabled)
    }

    @Test fun globalAndChannelStopsRemainIndependentAcrossRefreshAndRestart() {
        val enabled = PublicationActivation.restore(true, true).withBinding(false)
        assertTrue(enabled.globalEnabled); assertFalse(enabled.whatsAppEnabled)
        assertTrue(PublicationActivation.restore(enabled.globalEnabled, enabled.whatsAppEnabled).globalEnabled)
        val stopped = PublicationActivation.restore(false, true).withBinding(true)
        assertFalse(stopped.globalEnabled); assertTrue(stopped.whatsAppEnabled)
    }

    @Test fun unknownBootFlagCannotReadOrdinaryStorageOrRestorePermissionWhileLocked() {
        assertFalse(PublicationActivation.restoreBootPermission(false, null,
            { error("Credential storage is unavailable before first unlock") }, { error("Must not persist consent") }))
    }

    @Test fun firstUnlockedMigrationCopiesReadableGlobalStateAndPreservesAnExistingStop() {
        for ((global, legacy) in listOf(null to false, null to true, false to true, true to false)) {
            var saved: Boolean? = null
            val expected = PublicationActivation.restore(global, legacy).globalEnabled
            assertEquals(expected, PublicationActivation.restoreBootPermission(true, saved,
                { PublicationActivation.restore(global, legacy).globalEnabled }, { saved = it }))
            assertEquals(expected, saved)
            assertEquals(expected, PublicationActivation.restoreBootPermission(false, saved,
                { error("No CE read on reboot") }, { error("No restoration or attempt reset on reboot") }))
        }
        assertFalse(PublicationActivation.restoreBootPermission(true, false,
            { error("A saved stop must not be overwritten by migration") }, { error("No write") }))
    }

    @Test fun failedOrdinaryStopWriteStillBlocksBootRuntimeRefreshAndMigration() {
        var ordinary = true
        var boot: Boolean? = true
        assertThrows(IllegalStateException::class.java) {
            PublicationActivation.persistGlobal(false, { error("Synthetic CE write failure") }, { boot = it })
        }
        assertFalse(boot!!)
        assertFalse(PublicationActivation.restore(ordinary, true, boot).globalEnabled)
        assertFalse(PublicationActivation.restore(ordinary, true, boot).withBinding(true).globalEnabled)
        assertFalse(PublicationActivation.restoreBootPermission(true, boot, { ordinary }, { boot = it }))
        PublicationActivation.persistGlobal(true, { ordinary = it }, { boot = it })
        assertTrue(PublicationActivation.restore(ordinary, true, boot).globalEnabled)
    }

    @Test fun interruptedExplicitStartDoesNotReopenTheSavedStop() {
        var ordinary = false
        val boot = false
        assertThrows(IllegalStateException::class.java) {
            PublicationActivation.persistGlobal(true, { ordinary = it }, { error("Synthetic DP write failure") })
        }
        assertTrue(ordinary)
        assertFalse(PublicationActivation.restore(ordinary, true, boot).globalEnabled)
        assertFalse(BootUnlockPolicy.eligible(true, true, false, 10, 9, globalEnabled = boot))
    }

    @Test fun physicalReportContainsOnlyTheClosedRuntimeContract() {
        val value = NativeRuntimeState(false, true, true, false, true).toJson()
        assertEquals(setOf("contract_version", "global_enabled", "service_ready", "accessibility_enabled",
            "screen_unlocked", "media_permission"), value.keySet())
        assertEquals(1, value.getInt("contract_version"))
        assertFalse(value.getBoolean("global_enabled")); assertTrue(value.getBoolean("service_ready"))
        assertFalse(value.has("provider")); assertFalse(value.has("destination")); assertFalse(value.has("video_permission"))
        assertThrows(IllegalArgumentException::class.java) { NativeRuntimeState(true, true, false, true, true) }
    }

    @Test fun facebookNeverConstructsOrCallsAWhatsAppAdapterEvenWithACompatibleLookingPayload() {
        var constructed = 0
        assertThrows(IllegalArgumentException::class.java) {
            NativePublicationRouter.execute(PublicationProvider.FACEBOOK, JSONObject().put("platform", "WhatsApp")) {
                constructed++; error("Must not construct a fallback")
            }
        }
        assertEquals(0, constructed)
        assertFalse(PublicationProvider.FACEBOOK.adapterValidated)
    }

    @Test fun mismatchedPayloadCannotConstructAnAdapterAndMismatchedAdapterCannotExecute() {
        var executed = 0
        assertThrows(IllegalArgumentException::class.java) {
            NativePublicationRouter.execute(PublicationProvider.WHATSAPP_BUSINESS, JSONObject().put("platform", "Facebook")) {
                error("Must not construct")
            }
        }
        assertThrows(IllegalArgumentException::class.java) {
            NativePublicationRouter.execute(PublicationProvider.WHATSAPP_BUSINESS, JSONObject().put("platform", "WhatsApp")) {
                object : NativePublicationAdapter {
                    override val provider = PublicationProvider.FACEBOOK
                    override fun execute(payload: JSONObject) { executed++ }
                }
            }
        }
        assertEquals(0, executed)
    }

    @Test fun validatedWhatsAppRouteExecutesOnceWithOriginalPayload() {
        val payload = JSONObject().put("platform", "WhatsApp").put("count", 12)
        var executed = 0
        NativePublicationRouter.execute(PublicationProvider.WHATSAPP_BUSINESS, payload) {
            object : NativePublicationAdapter {
                override val provider = PublicationProvider.WHATSAPP_BUSINESS
                override fun execute(payload: JSONObject) { executed++; assertEquals(12, payload.getInt("count")) }
            }
        }
        assertEquals(1, executed)
    }
}
