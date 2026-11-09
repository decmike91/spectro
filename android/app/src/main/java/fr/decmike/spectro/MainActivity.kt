@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package fr.decmike.spectro

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Functions
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import fr.decmike.spectro.ui.AppViewModel
import fr.decmike.spectro.ui.Chips
import fr.decmike.spectro.ui.Conn
import fr.decmike.spectro.ui.KV
import fr.decmike.spectro.ui.SwitchRow
import fr.decmike.spectro.ui.Tab
import fr.decmike.spectro.ui.TextField1
import fr.decmike.spectro.ui.fmt
import fr.decmike.spectro.ui.screens.CalibScreen
import fr.decmike.spectro.ui.screens.LibraryScreen
import fr.decmike.spectro.ui.screens.LiveScreen
import fr.decmike.spectro.ui.screens.ProcessScreen
import fr.decmike.spectro.ui.screens.SequenceScreen
import fr.decmike.spectro.ui.theme.SpectroTheme

class MainActivity : ComponentActivity() {
    private val vm: AppViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val night by vm.nightMode.collectAsState()
            val keepOn by vm.keepScreenOn.collectAsState()
            LaunchedEffect(keepOn) {
                if (keepOn) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
            LaunchedEffect(Unit) { vm.intents.collect { startActivity(it) } }
            SpectroTheme(night) { AppRoot(vm) }
        }
    }
}

private fun Tab.icon(): ImageVector = when (this) {
    Tab.LIVE -> Icons.Filled.PlayArrow
    Tab.SEQ -> Icons.Filled.Repeat
    Tab.LIB -> Icons.Filled.Folder
    Tab.PROC -> Icons.Filled.Functions
    Tab.CALIB -> Icons.Filled.Build
}

@Composable
fun AppRoot(vm: AppViewModel) {
    val tab by vm.tab.collectAsState()
    val conn by vm.conn.collectAsState()
    val night by vm.nightMode.collectAsState()
    val st by vm.status.collectAsState()
    val snack = remember { SnackbarHostState() }
    var settings by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Spectro TCD1304")
                        val sub = when (conn) {
                            Conn.CONNECTED -> "connecté" + (st?.job?.let { " · ${it.name} ${it.index}/${it.count}" } ?: "") +
                                (if (st?.sim == true) " · simulateur" else "")
                            Conn.CONNECTING -> "connexion…"
                            Conn.DISCONNECTED -> "déconnecté"
                        }
                        Text(sub, style = MaterialTheme.typography.labelSmall)
                    }
                },
                actions = {
                    IconButton(onClick = { vm.setNight(!night) }) { Icon(Icons.Filled.DarkMode, "Mode nuit") }
                    IconButton(onClick = { settings = true }) {
                        Icon(if (conn == Conn.CONNECTED) Icons.Filled.Wifi else Icons.Filled.WifiOff, "Connexion",
                             tint = if (conn == Conn.CONNECTED) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
                    }
                    IconButton(onClick = { settings = true }) { Icon(Icons.Filled.Settings, "Réglages") }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                for (t in Tab.entries) {
                    NavigationBarItem(selected = t == tab, onClick = { vm.tab.value = t },
                                      icon = { Icon(t.icon(), t.label) }, label = { Text(t.label) })
                }
            }
        },
        snackbarHost = { SnackbarHost(snack) },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            when (tab) {
                Tab.LIVE -> LiveScreen(vm)
                Tab.SEQ -> SequenceScreen(vm)
                Tab.LIB -> LibraryScreen(vm)
                Tab.PROC -> ProcessScreen(vm)
                Tab.CALIB -> CalibScreen(vm)
            }
        }
    }

    if (settings) SettingsDialog(vm) { settings = false }
}

@Composable
private fun SettingsDialog(vm: AppViewModel, onClose: () -> Unit) {
    val host by vm.host.collectAsState()
    val found by vm.discovered.collectAsState()
    val st by vm.status.collectAsState()
    val night by vm.nightMode.collectAsState()
    val keepOn by vm.keepScreenOn.collectAsState()
    var h by remember { mutableStateOf(host) }

    LaunchedEffect(Unit) { vm.startDiscovery() }
    AlertDialog(
        onDismissRequest = { vm.stopDiscovery(); onClose() },
        title = { Text("Connexion et réglages") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TextField1("Adresse du Pi (ip:port)", h, { h = it }, Modifier.fillMaxWidth())
                Button(onClick = { vm.connect(h); vm.stopDiscovery(); onClose() }, modifier = Modifier.fillMaxWidth()) {
                    Text("Se connecter")
                }
                Text(if (found.isEmpty()) "Recherche du spectro sur le réseau…" else "Trouvé sur le réseau :",
                     style = MaterialTheme.typography.labelMedium)
                for ((name, hp) in found) {
                    TextButton(onClick = { h = hp; vm.connect(hp); vm.stopDiscovery(); onClose() }) { Text("$name  ($hp)") }
                }
                SwitchRow("Mode nuit (rouge)", night) { vm.setNight(it) }
                SwitchRow("Garder l'écran allumé", keepOn) { vm.setKeepOn(it) }
                st?.let { s ->
                    Text("Ventilateur", style = MaterialTheme.typography.labelMedium)
                    Chips(listOf("auto" to "Auto", "on" to "Marche", "off" to "Arrêt"), s.fan.mode) { vm.setFan(it) }
                    Text("Auto : coupé pendant les acquisitions (vibrations), sinon selon la température du Pi.",
                         style = MaterialTheme.typography.bodySmall)
                    KV("Serveur", "v" + s.version + if (s.sim) " (simulateur)" else "")
                    s.tempC?.let { KV("Température du Pi", fmt(it, 1) + " °C") }
                    KV("Ventilateur", (if (s.fan.running) "en marche" else "arrêté") + if (!s.fan.gpio) " (pas de GPIO)" else "")
                    KV("Espace libre", "${s.diskFreeMb} Mo")
                }
            }
        },
        confirmButton = { TextButton(onClick = { vm.stopDiscovery(); onClose() }) { Text("Fermer") } },
    )
}
