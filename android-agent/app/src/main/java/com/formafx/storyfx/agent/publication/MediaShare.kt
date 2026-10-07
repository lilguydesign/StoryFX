package com.formafx.storyfx.agent.publication

import android.content.ClipData
import android.content.ClipDescription
import android.content.Intent
import android.net.Uri

/** Build the ordered Android grant without opening WhatsApp or sending anything. */
object MediaShare {
    fun intent(media: ArrayList<Uri>, types: List<String>): Intent {
        require(media.size in 1..30 && media.size == types.size && media.toSet().size == media.size)
        val mime = MediaPlan.shareMime(types)
        val clip = ClipData(ClipDescription("StoryFX", types.distinct().toTypedArray()), ClipData.Item(media.first()))
        media.drop(1).forEach { clip.addItem(ClipData.Item(it)) }
        return Intent(Intent.ACTION_SEND_MULTIPLE).setPackage(PublicationPolicy.provider)
            .setType(mime).putParcelableArrayListExtra(Intent.EXTRA_STREAM, media)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION).apply { clipData = clip }
    }
}
