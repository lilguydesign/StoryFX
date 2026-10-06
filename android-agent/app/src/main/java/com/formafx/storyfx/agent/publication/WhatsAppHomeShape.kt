package com.formafx.storyfx.agent.publication

/** Read-only empty-status evidence requires the provider's Updates home, never a chat. */
object WhatsAppHomeShape {
    fun portrait(width: Int, height: Int) = width > 0 && height > width
    fun header(top: Int, height: Int) = top >= 0 && top < height * 0.20
    fun section(top: Int, height: Int) = top >= 0 && top < height * 0.35
    fun ownTile(centerX: Int, top: Int, width: Int, height: Int) =
        centerX >= 0 && centerX < width * 0.40 && top >= 0 && top < height * 0.50
    fun navigation(top: Int, height: Int) = top >= height * 0.65 && top < height
    fun empty(portrait: Boolean, header: Boolean, section: Boolean, ownTile: Boolean,
              ownStatus: Boolean, sendControl: Boolean) =
        portrait && header && section && ownTile && !ownStatus && !sendControl
}
