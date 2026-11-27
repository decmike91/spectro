@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package fr.decmike.spectro.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import fr.decmike.spectro.data.KINDS
import fr.decmike.spectro.data.kindLabel
import fr.decmike.spectro.math.SpectrumMath
import fr.decmike.spectro.ui.AppViewModel
import fr.decmike.spectro.ui.ChartSeries
import fr.decmike.spectro.ui.Chips
import fr.decmike.spectro.ui.Dropdown
import fr.decmike.spectro.ui.KV
import fr.decmike.spectro.ui.NumField
import fr.decmike.spectro.ui.Section
import fr.decmike.spectro.ui.SpectrumChart
import fr.decmike.spectro.ui.SwitchRow
import fr.decmike.spectro.ui.TextField1
import fr.decmike.spectro.ui.fmt
import fr.decmike.spectro.ui.theme.seriesColors
import fr.decmike.spectro.ui.toDoubleOr
import fr.decmike.spectro.ui.toIntOr

/** Spectre en direct, temps de pose, moyennes, noir, acquisition unique. */
@Composable
fun LiveScreen(vm: AppViewModel) {
    val st by vm.status.collectAsState()
    val frame by vm.live.collectAsState()
    val fps by vm.fps.collectAsState()
    val lib by vm.library.collectAsState()
    val ws by vm.workspace.collectAsState()
    val axisNm by vm.axisNm.collectAsState()
    val night by vm.nightMode.collectAsState()
    val colors = seriesColors(night)

    var tintMs by rememberSaveable { mutableStateOf("") }
    var avg by rememberSaveable { mutableStateOf("") }
    var darkId by rememberSaveable { mutableStateOf<String?>(null) }
    var overlay by rememberSaveable { mutableStateOf(-1L) }
    var name by rememberSaveable { mutableStateOf("etoile") }
    var kind by rememberSaveable { mutableStateOf("light") }
    var cursor by remember { mutableStateOf<Int?>(null) }

    val s = st
    if (tintMs.isEmpty() && s != null) tintMs = fmt(s.tintUs / 1000.0, 2)
    if (avg.isEmpty() && s != null) avg = s.averages.toString()
    val coeffs = s?.calib?.coeffs
    val toNm: ((Double) -> Double)? = if (axisNm && coeffs != null) { p -> SpectrumMath.polyval(coeffs, p) } else null
    val darks = lib.filter { it.kind == "dark" }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        val series = ArrayList<ChartSeries>()
        frame?.let { series.add(ChartSeries(it.values, colors[0], "direct")) }
        ws.firstOrNull { it.uid == overlay }?.let { series.add(ChartSeries(it.values, colors[1], it.name)) }
        SpectrumChart(series, Modifier.padding(4.dp), height = 300.dp, toNm = toNm, cursor = cursor,
                      onCursor = { cursor = it })

        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            val f = frame
            Text(fmt(fps, 1) + " sp/s", style = MaterialTheme.typography.bodySmall)
            Text("noir " + (f?.let { fmt(it.black, 0) } ?: "–"), style = MaterialTheme.typography.bodySmall)
            Text(
                "max brut " + (f?.maxRaw?.toString() ?: "–") + if (f?.saturated == true) "  SATURÉ" else "",
                style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold,
                color = if (f?.saturated == true) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
            )
            Text((s?.tempC?.let { fmt(it, 0) + " °C" } ?: ""), style = MaterialTheme.typography.bodySmall)
        }

        Section("Acquisition en direct") {
            SwitchRow("Spectre en direct", s?.live == true) { vm.setLive(it, darkId) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                NumField("Pose (ms)", tintMs, { tintMs = it }, Modifier.weight(1f))
                NumField("Moyennes", avg, { avg = it }, Modifier.weight(1f), decimal = false)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    val t = (tintMs.toDoubleOr(10.0) / 2).coerceAtLeast(0.01); tintMs = fmt(t, 2)
                    vm.setConfig(tintUs = (t * 1000).toLong())
                }) { Text("÷2") }
                OutlinedButton(onClick = {
                    val t = (tintMs.toDoubleOr(10.0) * 2).coerceAtMost(60000.0); tintMs = fmt(t, 2)
                    vm.setConfig(tintUs = (t * 1000).toLong())
                }) { Text("×2") }
                Button(onClick = {
                    vm.setConfig(tintUs = (tintMs.toDoubleOr(10.0) * 1000).toLong(), averages = avg.toIntOr(1).coerceAtLeast(1))
                }, modifier = Modifier.weight(1f)) { Text("Appliquer") }
            }
            SwitchRow("Soustraire le noir optique (pixels masqués)", s?.subBlack != false) { vm.setConfig(subBlack = it) }
            Dropdown("Noir soustrait", listOf<Pair<String?, String>>(null to "Aucun") + darks.map { it.id to it.name },
                     darkId, { darkId = it; if (s?.live == true) vm.setLive(true, it) })
            Dropdown("Superposer un spectre de l'espace de travail",
                     listOf(-1L to "Aucun") + ws.map { it.uid to it.name }, overlay, { overlay = it })
            SwitchRow("Axe en longueur d'onde (nm)", axisNm) { vm.setAxisNm(it) }
        }

        Section("Acquisition unique (enregistrée sur le Pi)") {
            TextField1("Nom", name, { name = it }, Modifier.fillMaxWidth())
            Chips(KINDS.filter { it != "result" }.map { it to kindLabel(it) }, kind) { kind = it }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.acquire(name, kind, darkId) }, enabled = s?.job == null,
                       modifier = Modifier.weight(1f)) { Text("Acquérir") }
                OutlinedButton(onClick = { vm.freezeLive(name) }, modifier = Modifier.weight(1f)) { Text("Figer le direct") }
            }
            Text("« Acquérir » utilise la pose et les moyennes ci-dessus. « Figer » copie le spectre affiché " +
                 "dans l'espace de travail du téléphone, sans l'enregistrer sur le Pi.",
                 style = MaterialTheme.typography.bodySmall)
        }

        s?.let {
            Section("Capteur") {
                KV("Mode", if (it.sim) "simulateur" else "capteur réel")
                KV("Pose / moyennes", fmt(it.tintUs / 1000.0, 2) + " ms × " + it.averages)
                KV("Ventilateur", it.fan.mode + if (it.fan.running) " (en marche)" else " (arrêté)")
                KV("Espace libre", "${it.diskFreeMb} Mo")
                it.error?.let { e -> KV("Erreur", e) }
            }
        }
    }
}
