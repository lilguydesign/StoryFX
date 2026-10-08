package com.formafx.storyfx.agent

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

interface AgentGateway {
    fun post(path: String, body: JSONObject): JSONObject
}

class AgentApi(server: String, private val token: String? = null) : AgentGateway {
    private val base = ServerAddress.validate(server, BuildConfig.DEBUG)

    override fun post(path: String, body: JSONObject): JSONObject {
        check(path.startsWith("/v1/") && !path.contains(".."))
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 15000
            connection.readTimeout = 15000
            connection.instanceFollowRedirects = false
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.setRequestProperty("Accept", "application/json")
            token?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val status = connection.responseCode
            if (status !in 200..299) {
                val invalid = if (status == 422 && body.has("diagnostics")) runCatching {
                    val raw = connection.errorStream?.bufferedReader(Charsets.UTF_8)?.use { reader ->
                        val buffer = CharArray(65537)
                        var count = 0
                        while (count < buffer.size) {
                            val read = reader.read(buffer, count, buffer.size - count)
                            if (read == -1) break
                            count += read
                        }
                        check(count <= 65536)
                        String(buffer, 0, count)
                    } ?: return@runCatching false
                    AgentErrorPolicy.invalidRequest(JSONObject(raw))
                }.getOrDefault(false) else false
                throw AgentRequestException(status, invalid)
            }
            val raw = connection.inputStream.bufferedReader(Charsets.UTF_8).use {
                val buffer = CharArray(131073)
                var count = 0
                while (count < buffer.size) {
                    val received = it.read(buffer, count, buffer.size - count)
                    if (received == -1) break
                    count += received
                }
                check(count <= 131072)
                String(buffer, 0, count)
            }
            return if (raw.isBlank()) JSONObject() else JSONObject(raw)
        } finally {
            connection.disconnect()
        }
    }

    fun completionCompatibility(): CompletionCompatibility = runCatching {
        val connection = URL(base + "/health").openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Accept", "application/json")
            if (connection.responseCode != 200) return@runCatching CompletionCompatibility.FULL
            val raw = connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                val buffer = CharArray(65537)
                var count = 0
                while (count < buffer.size) {
                    val read = reader.read(buffer, count, buffer.size - count)
                    if (read == -1) break
                    count += read
                }
                check(count <= 65536)
                String(buffer, 0, count)
            }
            AgentErrorPolicy.completionCompatibility(JSONObject(raw))
        } finally { connection.disconnect() }
    }.getOrDefault(CompletionCompatibility.FULL)
}

class AgentRequestException(val status: Int, val invalidRequest: Boolean = false) :
    Exception("Requête refusée (HTTP $status).")
