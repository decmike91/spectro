package fr.decmike.spectro.data

import org.json.JSONArray
import org.json.JSONObject

/** Types de spectres (identiques au serveur). */
val KINDS = listOf("light", "dark", "flat", "lamp", "ref", "result")
val KIND_LABELS = mapOf(
    "light" to "Objet", "dark" to "Noir", "flat" to "Flat", "lamp" to "Lampe",
    "ref" to "Référence", "result" to "Résultat",
)

fun kindLabel(k: String?) = KIND_LABELS[k] ?: (k ?: "?")

data class SpecMeta(
    val id: String, val name: String, val kind: String, val date: String,
    val tintUs: Long, val nFrames: Int, val combine: String?, val saturated: Boolean,
)

/** Spectre en mémoire (espace de travail de l'application). */
data class Spectrum(
    val uid: Long,
    val name: String,
    val kind: String,
    val values: DoubleArray,
    val date: String = "",
    val tintUs: Long = 0,
    val nFrames: Int = 1,
    val piId: String? = null,
    val history: List<String> = emptyList(),
) {
    val exposureS: Double get() = tintUs / 1e6 * nFrames
    override fun equals(other: Any?) = other is Spectrum && other.uid == uid
    override fun hashCode() = uid.hashCode()
}

data class Calib(
    val coeffs: DoubleArray,
    val points: List<Pair<Double, Double>> = emptyList(),
    val rms: Double? = null,
    val date: String? = null,
)

data class Job(
    val type: String, val name: String, val kind: String, val state: String,
    val index: Int, val count: Int, val progress: Double, val tintUs: Long,
    val intervalS: Double, val averages: Int, val combine: String,
    val results: List<String>, val error: String?, val started: String?,
)

data class FanState(val mode: String, val running: Boolean, val gpio: Boolean)

data class Status(
    val version: String, val sim: Boolean, val tintUs: Long, val averages: Int,
    val subBlack: Boolean, val live: Boolean, val liveDarkId: String?, val job: Job?,
    val tempC: Double?, val fan: FanState, val calib: Calib, val error: String?,
    val diskFreeMb: Long, val frames: Long,
)

data class LiveFrame(
    val t: Double, val tintUs: Long, val averages: Int, val black: Double,
    val maxRaw: Int, val saturated: Boolean, val values: DoubleArray,
)

// ---------------------------------------------------------------------------- JSON
private fun JSONObject.optStr(k: String): String? = if (has(k) && !isNull(k)) getString(k) else null
private fun JSONObject.optDbl(k: String): Double? = if (has(k) && !isNull(k)) getDouble(k) else null

fun JSONArray.toDoubleArray(): DoubleArray = DoubleArray(length()) { optDouble(it, 0.0) }

fun parseMeta(o: JSONObject) = SpecMeta(
    id = o.getString("id"), name = o.optString("name", o.getString("id")),
    kind = o.optString("kind", "light"), date = o.optString("date", ""),
    tintUs = o.optLong("tint_us", 0), nFrames = o.optInt("n_frames", 1),
    combine = o.optStr("combine"), saturated = o.optBoolean("saturated", false),
)

fun parseSpectrum(o: JSONObject, uid: Long): Spectrum {
    val hist = o.optJSONArray("history")
    return Spectrum(
        uid = uid, name = o.optString("name", "spectre"), kind = o.optString("kind", "light"),
        values = o.getJSONArray("values").toDoubleArray(), date = o.optString("date", ""),
        tintUs = o.optLong("tint_us", 0), nFrames = o.optInt("n_frames", 1), piId = o.optStr("id"),
        history = if (hist == null) emptyList() else List(hist.length()) { hist.getString(it) },
    )
}

fun spectrumToJson(s: Spectrum): JSONObject = JSONObject().apply {
    put("name", s.name); put("kind", s.kind); put("tint_us", s.tintUs); put("n_frames", s.nFrames)
    put("history", JSONArray(s.history))
    put("values", JSONArray().also { a -> s.values.forEach { a.put(if (it.isFinite()) it else 0.0) } })
}

fun parseCalib(o: JSONObject): Calib {
    val pts = o.optJSONArray("points")
    return Calib(
        coeffs = o.getJSONArray("coeffs").toDoubleArray(),
        points = if (pts == null) emptyList() else List(pts.length()) {
            val p = pts.getJSONArray(it); Pair(p.getDouble(0), p.getDouble(1))
        },
        rms = o.optDbl("rms"), date = o.optStr("date"),
    )
}

fun calibToJson(c: Calib): JSONObject = JSONObject().apply {
    put("coeffs", JSONArray().also { a -> c.coeffs.forEach { a.put(it) } })
    put("points", JSONArray().also { a -> c.points.forEach { (p, l) -> a.put(JSONArray().put(p).put(l)) } })
    c.rms?.let { put("rms", it) }
}

fun parseJob(o: JSONObject?): Job? {
    if (o == null) return null
    val r = o.optJSONArray("results")
    return Job(
        type = o.optString("type"), name = o.optString("name"), kind = o.optString("kind"),
        state = o.optString("state"), index = o.optInt("index"), count = o.optInt("count", 1),
        progress = o.optDouble("progress", 0.0), tintUs = o.optLong("tint_us"),
        intervalS = o.optDouble("interval_s", 0.0), averages = o.optInt("averages", 1),
        combine = o.optString("combine", "mean"),
        results = if (r == null) emptyList() else List(r.length()) { r.getString(it) },
        error = o.optStr("error"), started = o.optStr("started"),
    )
}

fun parseStatus(o: JSONObject): Status {
    val fan = o.optJSONObject("fan") ?: JSONObject()
    return Status(
        version = o.optString("version"), sim = o.optBoolean("sim"), tintUs = o.optLong("tint_us"),
        averages = o.optInt("averages", 1), subBlack = o.optBoolean("sub_black", true),
        live = o.optBoolean("live"), liveDarkId = o.optStr("live_dark_id"),
        job = parseJob(o.optJSONObject("job")), tempC = o.optDbl("temp_c"),
        fan = FanState(fan.optString("mode", "auto"), fan.optBoolean("running"), fan.optBoolean("gpio")),
        calib = parseCalib(o.getJSONObject("calib")), error = o.optStr("error"),
        diskFreeMb = o.optLong("disk_free_mb"), frames = o.optLong("frames"),
    )
}

fun parseFrame(o: JSONObject) = LiveFrame(
    t = o.optDouble("t"), tintUs = o.optLong("tint_us"), averages = o.optInt("averages", 1),
    black = o.optDouble("black", 0.0), maxRaw = o.optInt("max_raw"),
    saturated = o.optBoolean("saturated"), values = o.getJSONArray("values").toDoubleArray(),
)
