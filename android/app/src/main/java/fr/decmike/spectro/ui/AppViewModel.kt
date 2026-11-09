package fr.decmike.spectro.ui

import android.app.Application
import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import fr.decmike.spectro.data.Calib
import fr.decmike.spectro.data.Discovery
import fr.decmike.spectro.data.LiveFrame
import fr.decmike.spectro.data.SpecMeta
import fr.decmike.spectro.data.SpectroApi
import fr.decmike.spectro.data.Spectrum
import fr.decmike.spectro.data.Status
import fr.decmike.spectro.data.parseFrame
import fr.decmike.spectro.data.parseJob
import fr.decmike.spectro.data.parseStatus
import fr.decmike.spectro.math.Formats
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.atomic.AtomicLong

enum class Conn { DISCONNECTED, CONNECTING, CONNECTED }

enum class Tab(val label: String) { LIVE("Direct"), SEQ("Séquences"), LIB("Spectres"), PROC("Traitement"), CALIB("Étalonnage") }

/** État partagé de l'application et dialogue avec le serveur du Pi. */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("spectro", Context.MODE_PRIVATE)
    private val uidGen = AtomicLong(1)
    fun newUid() = uidGen.getAndIncrement()

    val host = MutableStateFlow(prefs.getString("host", "spectro.local:8080") ?: "")
    val conn = MutableStateFlow(Conn.DISCONNECTED)
    val status = MutableStateFlow<Status?>(null)
    val live = MutableStateFlow<LiveFrame?>(null)
    val fps = MutableStateFlow(0.0)
    val library = MutableStateFlow<List<SpecMeta>>(emptyList())
    val workspace = MutableStateFlow<List<Spectrum>>(emptyList())
    val discovered = MutableStateFlow<Map<String, String>>(emptyMap())
    val tab = MutableStateFlow(Tab.LIVE)
    val axisNm = MutableStateFlow(prefs.getBoolean("axisNm", true))
    val nightMode = MutableStateFlow(prefs.getBoolean("night", false))
    val keepScreenOn = MutableStateFlow(prefs.getBoolean("keepOn", true))

    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 8)
    val messages: SharedFlow<String> = _messages
    private val _intents = MutableSharedFlow<Intent>(extraBufferCapacity = 2)
    val intents: SharedFlow<Intent> = _intents

    private var api: SpectroApi? = null
    private var socket: WebSocket? = null
    private var reconnectJob: Job? = null
    private var lastFrameT = 0L
    private var lastJobState: String? = null
    private val discovery = Discovery(app) { name, hp ->
        discovered.value = discovered.value + (name to hp)
    }

    init {
        connect(host.value)
    }

    fun say(msg: String) { _messages.tryEmit(msg) }

    private fun launchSafe(what: String, block: suspend (SpectroApi) -> Unit) {
        val a = api
        if (a == null) { say("Pas connecté au spectro"); return }
        viewModelScope.launch {
            try { block(a) } catch (e: Exception) { say("$what : ${e.message ?: e.javaClass.simpleName}") }
        }
    }

    // ------------------------------------------------------------------ réglages locaux
    fun setAxisNm(v: Boolean) { axisNm.value = v; prefs.edit().putBoolean("axisNm", v).apply() }
    fun setNight(v: Boolean) { nightMode.value = v; prefs.edit().putBoolean("night", v).apply() }
    fun setKeepOn(v: Boolean) { keepScreenOn.value = v; prefs.edit().putBoolean("keepOn", v).apply() }

    fun startDiscovery() { discovered.value = emptyMap(); discovery.start() }
    fun stopDiscovery() = discovery.stop()

    // ------------------------------------------------------------------ connexion
    fun connect(h: String) {
        host.value = h
        prefs.edit().putString("host", h).apply()
        socket?.close(1000, null)
        reconnectJob?.cancel()
        val a = SpectroApi(h)
        api = a
        conn.value = Conn.CONNECTING
        viewModelScope.launch {
            try {
                status.value = a.status()
                refreshLibrary()
                openSocket(a)
            } catch (e: Exception) {
                conn.value = Conn.DISCONNECTED
                say("Connexion impossible à ${a.base} : ${e.message}")
                scheduleReconnect(a)
            }
        }
    }

    private fun scheduleReconnect(a: SpectroApi) {
        reconnectJob?.cancel()
        reconnectJob = viewModelScope.launch {
            delay(5000)
            if (api === a && conn.value != Conn.CONNECTED) {
                try {
                    status.value = a.status()
                    openSocket(a)
                } catch (e: Exception) {
                    scheduleReconnect(a)
                }
            }
        }
    }

    private fun openSocket(a: SpectroApi) {
        socket = a.openSocket(object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                conn.value = Conn.CONNECTED
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val o = JSONObject(text)
                    when (o.optString("type")) {
                        "frame" -> {
                            val now = System.currentTimeMillis()
                            if (lastFrameT > 0) fps.value = 0.7 * fps.value + 0.3 * (1000.0 / (now - lastFrameT).coerceAtLeast(1))
                            lastFrameT = now
                            live.value = parseFrame(o)
                        }
                        "status" -> status.value = parseStatus(o.getJSONObject("status"))
                        "job" -> {
                            val j = parseJob(o.getJSONObject("job")) ?: return
                            status.value = status.value?.copy(job = if (j.state in setOf("done", "stopped", "error")) null else j)
                            if (j.state != lastJobState && j.state in setOf("done", "stopped", "error")) {
                                say(when (j.state) {
                                    "done" -> "« ${j.name} » terminé (${j.results.size} spectre(s) enregistré(s))"
                                    "stopped" -> "« ${j.name} » arrêté"
                                    else -> "Erreur : ${j.error}"
                                })
                                refreshLibrary()
                            }
                            lastJobState = j.state
                        }
                    }
                } catch (_: Exception) {
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (api === a) {
                    conn.value = Conn.DISCONNECTED
                    scheduleReconnect(a)
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (api === a && code != 1000) {
                    conn.value = Conn.DISCONNECTED
                    scheduleReconnect(a)
                }
            }
        })
    }

    override fun onCleared() {
        socket?.close(1000, null)
        discovery.stop()
    }

    // ------------------------------------------------------------------ acquisition
    fun setConfig(tintUs: Long? = null, averages: Int? = null, subBlack: Boolean? = null) =
        launchSafe("Réglage") { status.value = it.config(tintUs, averages, subBlack) }

    fun setLive(on: Boolean, darkId: String?) = launchSafe("Direct") { status.value = it.live(on, darkId) }

    fun acquire(name: String, kind: String, darkId: String?) = launchSafe("Acquisition") {
        val st = status.value ?: return@launchSafe
        it.acquire(name, kind, st.tintUs, st.averages, darkId)
        say("Acquisition lancée")
    }

    fun startSequence(name: String, kind: String, count: Int, tintUs: Long, averages: Int, intervalS: Double,
                      combine: String, darkId: String?, saveIndividual: Boolean) = launchSafe("Séquence") {
        it.startSequence(name, kind, count, tintUs, averages, intervalS, combine, darkId, saveIndividual)
        lastJobState = "queued"
        status.value = it.status()
    }

    fun stopSequence() = launchSafe("Arrêt") { it.stopSequence() }

    fun setFan(mode: String) = launchSafe("Ventilateur") { it.fan(mode); status.value = it.status() }

    /** Copie le spectre en direct dans l'espace de travail. */
    fun freezeLive(name: String, kind: String = "light") {
        val f = live.value ?: run { say("Aucun spectre en direct"); return }
        addToWorkspace(Spectrum(newUid(), name, kind, f.values.copyOf(), now(), f.tintUs, f.averages,
                                history = listOf("figé depuis le direct")))
        say("« $name » ajouté à l'espace de travail")
    }

    // ------------------------------------------------------------------ bibliothèque du Pi
    fun refreshLibrary() = launchSafe("Liste") { library.value = it.list() }

    fun loadToWorkspace(ids: List<String>) = launchSafe("Chargement") { a ->
        val loaded = ids.map { a.get(it, newUid()) }
        workspace.value = workspace.value + loaded
        say("${loaded.size} spectre(s) dans l'espace de travail")
    }

    fun deleteOnPi(id: String) = launchSafe("Suppression") { it.delete(id); refreshLibrary() }

    fun renameOnPi(id: String, name: String) = launchSafe("Renommage") { it.rename(id, name); refreshLibrary() }

    fun exportFromPi(id: String, fmt: String) = launchSafe("Export") { a ->
        val bytes = a.download(id, fmt)
        share("$id.$fmt", bytes, if (fmt == "csv") "text/csv" else "application/octet-stream")
    }

    // ------------------------------------------------------------------ espace de travail
    fun addToWorkspace(s: Spectrum) { workspace.value = workspace.value + s }
    fun removeFromWorkspace(uid: Long) { workspace.value = workspace.value.filterNot { it.uid == uid } }
    fun renameInWorkspace(uid: Long, name: String) {
        workspace.value = workspace.value.map { if (it.uid == uid) it.copy(name = name) else it }
    }

    fun saveToPi(s: Spectrum) = launchSafe("Enregistrement") { a ->
        val id = a.save(s)
        workspace.value = workspace.value.map { if (it.uid == s.uid) it.copy(piId = id) else it }
        refreshLibrary()
        say("Enregistré sur le Pi : $id")
    }

    fun exportLocal(s: Spectrum, fmt: String) {
        val coeffs = status.value?.calib?.coeffs
        val safe = s.name.replace(Regex("[^A-Za-z0-9_-]+"), "_").ifBlank { "spectre" }
        try {
            if (fmt == "csv") {
                val txt = Formats.csv(s.name, s.values, coeffs, mapOf("type" to s.kind, "tint_us" to s.tintUs))
                share("$safe.csv", txt.toByteArray(), "text/csv")
            } else {
                share("$safe.fits", Formats.fits(s.name, s.values, coeffs, s.exposureS, s.date, s.kind),
                      "application/octet-stream")
            }
        } catch (e: Exception) {
            say("Export : ${e.message}")
        }
    }

    private fun share(fileName: String, bytes: ByteArray, mime: String) {
        val ctx = getApplication<Application>()
        val dir = File(ctx.cacheDir, "exports").apply { mkdirs() }
        val f = File(dir, fileName)
        f.writeBytes(bytes)
        val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", f)
        val send = Intent(Intent.ACTION_SEND).apply {
            type = mime
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, fileName)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        _intents.tryEmit(Intent.createChooser(send, "Partager $fileName"))
    }

    // ------------------------------------------------------------------ étalonnage
    fun saveCalibration(c: Calib) = launchSafe("Étalonnage") { a ->
        val saved = a.putCalib(c)
        status.value = status.value?.copy(calib = saved)
        say("Étalonnage enregistré sur le Pi")
    }

    companion object {
        fun now(): String = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME).take(19)
    }
}
