package com.formafx.storyfx.agent.publication

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import org.json.JSONObject

object AlbumMedia {
    fun permission() = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_IMAGES
        else Manifest.permission.READ_EXTERNAL_STORAGE

    fun allowed(context: Context) = context.checkSelfPermission(permission()) == PackageManager.PERMISSION_GRANTED
    fun videoPermission() = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_VIDEO else permission()
    fun videosAllowed(context: Context) = context.checkSelfPermission(videoPermission()) == PackageManager.PERMISSION_GRANTED
    fun permissions() = arrayOf(permission(), videoPermission()).distinct().toTypedArray()

    private fun candidates(context: Context, album: String, video: Boolean): List<MediaSelection.Candidate<Uri>> {
        val base = if (video) MediaStore.Video.Media.EXTERNAL_CONTENT_URI else MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        val projection = arrayOf(MediaStore.Images.Media._ID, MediaStore.Images.Media.BUCKET_ID)
        val result = mutableListOf<MediaSelection.Candidate<Uri>>()
        context.contentResolver.query(base, projection + arrayOf(MediaStore.Images.Media.DATE_ADDED, MediaStore.Images.Media.DATE_TAKEN),
            "${MediaStore.Images.Media.BUCKET_DISPLAY_NAME} = ?", arrayOf(album),
            "${MediaStore.Images.Media.DATE_ADDED} DESC, ${MediaStore.Images.Media._ID} DESC")?.use { cursor ->
            while (cursor.moveToNext()) {
                check(result.size < 20000)
                result.add(MediaSelection.Candidate(ContentUris.withAppendedId(base, cursor.getLong(0)),
                    cursor.getLong(1), cursor.getLong(2), cursor.getLong(0), if (video) "video" else "image",
                    if (cursor.isNull(3)) null else cursor.getLong(3)))
            }
        }
        return result
    }

    fun batch(context: Context, payload: JSONObject): ArrayList<Uri> {
        check(allowed(context))
        val result = arrayListOf<Uri>()
        for (part in MediaPlan.parts(payload)) {
            if (part.kind == "video") check(videosAllowed(context))
            val available = if (part.kind == "video") candidates(context, part.album, true) else
                candidates(context, part.album, false) + if (videosAllowed(context)) candidates(context, part.album, true) else emptyList()
            result.addAll(MediaSelection.select(available, part.count, result.toSet()))
        }
        check(result.size == MediaPlan.total(payload))
        result.forEach { uri -> context.contentResolver.openFileDescriptor(uri, "r")?.use { check(it.statSize != 0L) }
            ?: error("ALBUM_MEDIA_UNAVAILABLE") }
        return result
    }

    fun share(context: Context, media: ArrayList<Uri>) {
        check(media.isNotEmpty() && media.size <= 30)
        val types = media.map { requireNotNull(context.contentResolver.getType(it)) }
        val intent = MediaShare.intent(media, types)
        check(intent.resolveActivity(context.packageManager) != null)
        context.startActivity(intent)
    }
}
