package com.formafx.storyfx.agent.update

import java.io.File
import java.net.URL
import java.security.MessageDigest
import javax.net.ssl.HttpsURLConnection

object UpdateDownload {
    private const val maxApk = 128L * 1024 * 1024
    private fun connection(url: String): HttpsURLConnection =
        (URL(url).openConnection() as HttpsURLConnection).apply {
            instanceFollowRedirects = false
            connectTimeout = 15000
            readTimeout = 30000
            setRequestProperty("Accept-Encoding", "identity")
        }
    fun latest(): UpdateRelease {
        val connection = connection(UpdateRelease.catalog)
        try {
            require(connection.responseCode == 200)
            val bytes = connection.inputStream.use { it.readBytesLimited(65536) }
            return UpdateRelease.parse(bytes.toString(Charsets.UTF_8))
        } finally { connection.disconnect() }
    }
    fun download(folder: File, release: UpdateRelease, progress: (Int) -> Unit): File {
        require(folder.mkdirs() || folder.isDirectory)
        val part = File(folder, "candidate.part")
        val ready = File(folder, "candidate.apk")
        val connection = connection(release.url)
        try {
            require(connection.responseCode == 200)
            val expected = connection.contentLengthLong
            require(expected <= maxApk)
            var total = 0L
            val digest = MessageDigest.getInstance("SHA-256")
            connection.inputStream.use { input -> part.outputStream().use { output ->
                val buffer = ByteArray(65536)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    require(total <= maxApk)
                    digest.update(buffer, 0, count)
                    output.write(buffer, 0, count)
                    if (expected > 0) progress((100 * total / expected).toInt().coerceIn(0, 100))
                }
            } }
            require(total > 0 && (expected < 0 || total == expected))
            require(hex(digest.digest()) == release.sha256)
            require(!ready.exists() || ready.delete())
            require(part.renameTo(ready))
            return ready
        } catch (failure: Exception) {
            part.delete()
            throw failure
        } finally { connection.disconnect() }
    }
    fun hash(file: File): String = file.inputStream().use { input ->
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(65536)
        while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        hex(digest.digest())
    }
    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun java.io.InputStream.readBytesLimited(limit: Int): ByteArray {
        val output = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val count = read(buffer)
            if (count < 0) break
            require(output.size() + count <= limit)
            output.write(buffer, 0, count)
        }
        return output.toByteArray()
    }
}
