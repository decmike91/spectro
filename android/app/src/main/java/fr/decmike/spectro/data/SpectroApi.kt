package fr.decmike.spectro.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class ApiException(msg: String) : IOException(msg)

/** Client de l'API HTTP / WebSocket du serveur du Pi Zero (logiciel/serveur/spectro_server.py). */
class SpectroApi(host: String) {
    val base: String = normalize(host)

    private val http = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .pingInterval(15, TimeUnit.SECONDS)
        .build()

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()

        fun normalize(host: String): String {
            var h = host.trim().removeSuffix("/")
            if (!h.startsWith("http://") && !h.startsWith("https://")) h = "http://$h"
            val afterScheme = h.substringAfter("://")
            if (!afterScheme.contains(':')) h = "$h:8080"
            return h
        }
    }

    private fun call(method: String, path: String, body: JSONObject? = null): Response {
        val rb = when {
            body != null -> body.toString().toRequestBody(JSON)
            method == "POST" || method == "PUT" || method == "PATCH" -> "{}".toRequestBody(JSON)
            else -> null
        }
        val req = Request.Builder().url(base + path).method(method, rb).build()
        return http.newCall(req).execute()
    }

    private suspend fun json(method: String, path: String, body: JSONObject? = null): Any? =
        withContext(Dispatchers.IO) {
            call(method, path, body).use { r ->
                val text = r.body?.string() ?: ""
                val o = try { JSONObject(text) } catch (e: Exception) {
                    throw ApiException("réponse invalide (${r.code})")
                }
                if (!o.optBoolean("ok", false)) throw ApiException(o.optString("error", "erreur ${r.code}"))
                if (o.has("data") && !o.isNull("data")) o.get("data") else null
            }
        }

    suspend fun status(): Status = parseStatus(json("GET", "/api/status") as JSONObject)

    suspend fun config(tintUs: Long? = null, averages: Int? = null, subBlack: Boolean? = null): Status {
        val b = JSONObject()
        tintUs?.let { b.put("tint_us", it) }; averages?.let { b.put("averages", it) }
        subBlack?.let { b.put("sub_black", it) }
        return parseStatus(json("POST", "/api/config", b) as JSONObject)
    }

    suspend fun live(on: Boolean, darkId: String?): Status =
        parseStatus(json("POST", "/api/live", JSONObject().put("on", on).put("dark_id", darkId ?: JSONObject.NULL)) as JSONObject)

    suspend fun acquire(name: String, kind: String, tintUs: Long, averages: Int, darkId: String?) {
        json("POST", "/api/acquire", JSONObject().put("name", name).put("kind", kind).put("tint_us", tintUs)
            .put("averages", averages).put("dark_id", darkId ?: JSONObject.NULL))
    }

    suspend fun startSequence(
        name: String, kind: String, count: Int, tintUs: Long, averages: Int, intervalS: Double,
        combine: String, darkId: String?, saveIndividual: Boolean,
    ) {
        json("POST", "/api/sequence", JSONObject().put("name", name).put("kind", kind).put("count", count)
            .put("tint_us", tintUs).put("averages", averages).put("interval_s", intervalS)
            .put("combine", combine).put("dark_id", darkId ?: JSONObject.NULL)
            .put("save_individual", saveIndividual))
    }

    suspend fun stopSequence() { json("POST", "/api/sequence/stop") }

    suspend fun list(): List<SpecMeta> {
        val a = json("GET", "/api/spectra") as? JSONArray ?: return emptyList()
        return List(a.length()) { parseMeta(a.getJSONObject(it)) }
    }

    suspend fun get(id: String, uid: Long): Spectrum = parseSpectrum(json("GET", "/api/spectra/$id") as JSONObject, uid)

    suspend fun save(s: Spectrum): String = (json("POST", "/api/spectra", spectrumToJson(s)) as JSONObject).getString("id")

    suspend fun rename(id: String, name: String) { json("PATCH", "/api/spectra/$id", JSONObject().put("name", name)) }

    suspend fun delete(id: String) { json("DELETE", "/api/spectra/$id") }

    suspend fun download(id: String, fmt: String): ByteArray = withContext(Dispatchers.IO) {
        call("GET", "/api/spectra/$id/$fmt").use { r ->
            if (!r.isSuccessful) throw ApiException("export impossible (${r.code})")
            r.body?.bytes() ?: ByteArray(0)
        }
    }

    suspend fun putCalib(c: Calib): Calib = parseCalib(json("PUT", "/api/calibration", calibToJson(c)) as JSONObject)

    suspend fun fan(mode: String) { json("POST", "/api/fan", JSONObject().put("mode", mode)) }

    fun openSocket(listener: WebSocketListener): WebSocket {
        val wsUrl = base.replaceFirst("http", "ws") + "/ws"
        return http.newWebSocket(Request.Builder().url(wsUrl).build(), listener)
    }
}
