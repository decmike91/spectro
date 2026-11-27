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
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
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

/** Séquences d'acquisition exécutées par le Pi (continuent même si le téléphone se déconnecte). */
@Composable
fun SequenceScreen(vm: AppViewModel) {
    val st by vm.status.collectAsState()
    val frame by vm.live.collectAsState()
    val lib by vm.library.collectAsState()
    val axisNm by vm.axisNm.collectAsState()
    val night by vm.nightMode.collectAsState()

    var name by rememberSaveable { mutableStateOf("vega") }
    var kind by rememberSaveable { mutableStateOf("light") }
    var count by rememberSaveable { mutableStateOf("20") }
    var tintMs by rememberSaveable { mutableStateOf("500") }
    var avg by rememberSaveable { mutableStateOf("1") }
    var interval by rememberSaveable { mutableStateOf("0") }
    var combine by rememberSaveable { mutableStateOf("mean") }
    var darkId by rememberSaveable { mutableStateOf<String?>(null) }
    var individual by rememberSaveable { mutableStateOf(false) }

    val job = st?.job
    val coeffs = st?.calib?.coeffs
    val toNm: ((Double) -> Double)? = if (axisNm && coeffs != null) { p -> SpectrumMath.polyval(coeffs, p) } else null
    val darks = lib.filter { it.kind == "dark" }

    fun start(k: String = kind, n: String = name, d: String? = darkId) {
        vm.startSequence(n, k, count.toIntOr(10).coerceAtLeast(1), (tintMs.toDoubleOr(100.0) * 1000).toLong(),
                         avg.toIntOr(1).coerceAtLeast(1), interval.toDoubleOr(0.0).coerceAtLeast(0.0), combine, d, individual)
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        if (job != null) {
            Section("En cours : ${job.name} (${kindLabel(job.kind)})") {
                LinearProgressIndicator(progress = { job.progress.toFloat() }, modifier = Modifier.fillMaxWidth())
                val perShot = job.tintUs / 1e6 * (job.averages + 1) + job.intervalS + 0.02
                val remain = (job.count - job.index) * perShot
                KV("Pose", "${job.index} / ${job.count}")
                KV("Temps restant estimé", if (remain > 90) fmt(remain / 60, 1) + " min" else fmt(remain, 0) + " s")
                KV("État", job.state)
                Button(onClick = { vm.stopSequence() }, modifier = Modifier.fillMaxWidth(),
                       colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
                    Text("Arrêter la séquence")
                }
            }
            frame?.let {
                SpectrumChart(listOf(ChartSeries(it.values, seriesColors(night)[0], "dernière pose")),
                              Modifier.padding(4.dp), height = 220.dp, toNm = toNm)
            }
        }

        Section("Nouvelle séquence") {
            TextField1("Nom (objet)", name, { name = it }, Modifier.fillMaxWidth())
            Chips(KINDS.filter { it != "result" }.map { it to kindLabel(it) }, kind) { kind = it }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                NumField("Nombre de poses", count, { count = it }, Modifier.weight(1f), decimal = false)
                NumField("Pose (ms)", tintMs, { tintMs = it }, Modifier.weight(1f))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                NumField("Lectures moyennées / pose", avg, { avg = it }, Modifier.weight(1f), decimal = false)
                NumField("Intervalle (s)", interval, { interval = it }, Modifier.weight(1f))
            }
            Text("Combinaison des poses", style = MaterialTheme.typography.labelMedium)
            Chips(listOf("mean" to "Moyenne", "median" to "Médiane", "sum" to "Somme", "none" to "Aucune"), combine) { combine = it }
            Dropdown("Noir à soustraire de chaque pose", listOf<Pair<String?, String>>(null to "Aucun") + darks.map { it.id to it.name },
                     darkId, { darkId = it })
            SwitchRow("Enregistrer aussi chaque pose", individual || combine == "none") { individual = it }
            val total = count.toIntOr(1) * (tintMs.toDoubleOr(0.0) / 1000 * (avg.toIntOr(1) + 1) + interval.toDoubleOr(0.0))
            Text("Durée estimée : " + if (total > 90) fmt(total / 60, 1) + " min" else fmt(total, 0) + " s",
                 style = MaterialTheme.typography.bodySmall)
            Button(onClick = { start() }, enabled = job == null, modifier = Modifier.fillMaxWidth()) { Text("Lancer la séquence") }
        }

        Section("Raccourcis") {
            Text("Mêmes réglages de pose, combinaison par médiane :", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { combine = "median"; start("dark", "noir_" + tintMs.trim() + "ms", null) },
                               enabled = job == null, modifier = Modifier.weight(1f)) { Text("Série de noirs") }
                OutlinedButton(onClick = { combine = "median"; start("lamp", "lampe", darkId) },
                               enabled = job == null, modifier = Modifier.weight(1f)) { Text("Série lampe") }
                OutlinedButton(onClick = { combine = "median"; start("flat", "flat", darkId) },
                               enabled = job == null, modifier = Modifier.weight(1f)) { Text("Série flat") }
            }
            Text("Le Pi exécute la séquence seul : vous pouvez fermer l'application, le résultat apparaîtra dans « Spectres ».",
                 style = MaterialTheme.typography.bodySmall)
        }
    }
}
