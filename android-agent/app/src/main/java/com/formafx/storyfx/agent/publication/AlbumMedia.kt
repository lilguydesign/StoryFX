package com.formafx.storyfx.agent.publication

import android.Manifest
import android.content.ClipData
import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.MediaStore

object AlbumMedia {
    fun permission() = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_IMAGES
        else Manifest.permission.READ_EXTERNAL_STORAGE

    fun allowed(context: Context) = context.checkSelfPermission(permission()) == PackageManager.PERMISSION_GRANTED

    fun images(context: Context, album: String, count: Int): ArrayList<Uri> {
        check(allowed(context) && count in 1..30 && album.isNotBlank())
        val base = MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        val projection = arrayOf(MediaStore.Images.Media._ID, MediaStore.Images.Media.BUCKET_ID)
        val result = arrayListOf<Uri>()
        val buckets = mutableSetOf<Long>()
        context.contentResolver.query(base, projection,
            "${MediaStore.Images.Media.BUCKET_DISPLAY_NAME} = ?", arrayOf(album),
            "${MediaStore.Images.Media.DATE_ADDED} DESC, ${MediaStore.Images.Media._ID} DESC")?.use { cursor ->
            while (cursor.moveToNext()) {
                buckets.add(cursor.getLong(1))
                if (result.size < count) result.add(ContentUris.withAppendedId(base, cursor.getLong(0)))
            }
        }
        check(buckets.size == 1 && result.size == count)
        result.forEach { uri -> context.contentResolver.openFileDescriptor(uri, "r")?.use { check(it.statSize != 0L) }
            ?: error("ALBUM_MEDIA_UNAVAILABLE") }
        return result
    }

    fun share(context: Context, media: ArrayList<Uri>) {
        check(media.isNotEmpty() && media.size <= 30)
        val clip = ClipData.newUri(context.contentResolver, "StoryFX", media.first())
        media.drop(1).forEach { clip.addItem(ClipData.Item(it)) }
        val intent = Intent(Intent.ACTION_SEND_MULTIPLE).setPackage(PublicationPolicy.provider)
            .setType("image/*").putParcelableArrayListExtra(Intent.EXTRA_STREAM, media)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.clipData = clip
        check(intent.resolveActivity(context.packageManager) != null)
        context.startActivity(intent)
    }
}
