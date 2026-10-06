package com.formafx.storyfx.agent.publication

/** Reject whole-window or multi-tab containers when resolving a precise provider control. */
object ProviderClickShape {
    fun accepts(width: Int, height: Int, rootWidth: Int, rootHeight: Int, navigation: Boolean): Boolean =
        width > 0 && height > 0 && rootWidth > 0 && rootHeight > 0 && width <= rootWidth && height <= rootHeight &&
            width.toLong() * height * 5 <= rootWidth.toLong() * rootHeight &&
            (!navigation || width * 100L <= rootWidth * 35L)
}
