package com.formafx.storyfx.agent.update

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import java.io.File
import java.security.MessageDigest

class UpdateVerifier(private val context: Context) {
    @Suppress("DEPRECATION")
    fun verify(file: File, release: UpdateRelease) {
        val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES
            else PackageManager.GET_SIGNATURES
        val installed = context.packageManager.getPackageInfo(context.packageName, flags)
        val archive = context.packageManager.getPackageArchiveInfo(file.absolutePath, flags)
            ?: error("APK_INVALID")
        require(archive.packageName == context.packageName)
        require(code(archive) == release.code && archive.versionName == release.version)
        require(code(archive) > code(installed))
        require(UpdateDownload.hash(file) == release.sha256)
        val current = signers(installed)
        require(current.isNotEmpty() && current == signers(archive))
    }
    @Suppress("DEPRECATION")
    private fun code(info: PackageInfo): Long = if (Build.VERSION.SDK_INT >= 28)
        info.longVersionCode else info.versionCode.toLong()
    @Suppress("DEPRECATION")
    private fun signers(info: PackageInfo): Set<String> {
        val signatures = if (Build.VERSION.SDK_INT >= 28)
            info.signingInfo?.apkContentsSigners.orEmpty() else info.signatures.orEmpty()
        return signatures.map { signature ->
            MessageDigest.getInstance("SHA-256").digest(signature.toByteArray())
                .joinToString("") { "%02x".format(it.toInt() and 255) }
        }.toSet()
    }
}
