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
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import fr.decmike.spectro.data.Calib
import fr.decmike.spectro.math.LineCatalog
import fr.decmike.spectro.math.PolyFit
import fr.decmike.spectro.math.RefLine
import fr.decmike.spectro.math.SpectrumMath
import fr.decmike.spectro.ui.AppViewModel
import fr.decmike.spectro.ui.ChartMarker
import fr.decmike.spectro.ui.ChartSeries
import fr.decmike.spectro.ui.Chips
import fr.decmike.spectro.ui.Dropdown
import fr.decmike.spectro.ui.KV
import fr.decmike.spectro.ui.Section
import fr.decmike.spectro.ui.SpectrumChart
import fr.decmike.spectro.ui.fmt
import fr.decmike.spectro.ui.theme.seriesColors
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/** Étalonnage en longueur d'onde avec une lampe (néon, mercure, argon, fluocompacte…). */
@Composable
fun CalibScreen(vm: AppViewModel) {
    val ws by vm.workspace.collectAsState()
    val st by vm.status.collectAsState()
    val night by vm.nightMode.collectAsState()
    val colors = seriesColors(night)

    var srcUid by remember { mutableStateOf(-1L) }
    var lampKey by remember { mutableStateOf(LineCatalog.LAMPS.keys.first()) }
    var order by remember { mutableStateOf(2) }
    var points by remember { mutableStateOf(listOf<Pair<Double, RefLine>>()) }
    var fit by remember { mutableStateOf<PolyFit?>(null) }
    var cursor by remember { mutableStateOf<Int?>(null) }
    var manualNm by remember { mutableStateOf<Double?>(null) }

    val src = ws.firstOrNull { it.uid == srcUid } ?: ws.lastOrNull { it.kind == "lamp" } ?: ws.lastOrNull()
    val lines = LineCatalog.LAMPS[lampKey] ?: LineCatalog.NEON
    val current = st?.calib?.coeffs ?: doubleArrayOf(350.0, 0.135, -2e-6)
    val model = fit?.coeffs ?: current

    fun refit(pts: List<Pair<Double, RefLine>>) {
        points = pts.sortedBy { it.first }
        fit = if (points.size >= 2) {
            val px = points.map { it.first }.toDoubleArray()
            val nm = points.map { it.second.nm }.toDoubleArray()
            SpectrumMath.polyfit(px, nm, min(order, points.size - 1))
        } else null
    }

    /** Pic le plus proche du curseur (±12 px), position sous-pixel. */
    fun snapped(): Double? {
        val s = src ?: return null
        val c = cursor ?: return null
        val a = max(1, c - 12); val b = min(s.values.size - 2, c + 12)
        var best = c
        for (i in a..b) if (s.values[i] > s.values[best]) best = i
        return SpectrumMath.gaussPeak(s.values, best)
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        val markers = points.map { (p, l) -> ChartMarker(p, fmt(l.nm, 2) + " " + l.label, colors[1]) }
        SpectrumChart(
            src?.let { listOf(ChartSeries(it.values, colors[0], it.name)) } ?: emptyList(),
            Modifier.padding(4.dp), height = 280.dp, toNm = null, markers = markers,
            cursor = cursor, onCursor = { cursor = it; manualNm = null },
        )
        cursor?.let { c ->
            Text("Curseur : pixel $c ≈ " + fmt(SpectrumMath.polyval(model, c.toDouble()), 2) + " nm",
                 Modifier.padding(horizontal = 12.dp), style = MaterialTheme.typography.bodySmall)
        }

        Section("Spectre de lampe") {
            Dropdown("Spectre", ws.map { it.uid to it.name }, src?.uid ?: -1L, { srcUid = it })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { vm.freezeLive("lampe", "lamp"); srcUid = -1L },
                               modifier = Modifier.weight(1f)) { Text("Capturer le direct") }
            }
            Dropdown("Lampe", LineCatalog.LAMPS.keys.map { it to it }, lampKey, { lampKey = it })
            Text("Ordre du polynôme", style = MaterialTheme.typography.labelMedium)
            Chips(listOf(1 to "1 (linéaire)", 2 to "2", 3 to "3"), order) { order = it; refit(points) }
        }

        Section("Identification des raies") {
            src?.let { s ->
                if (SpectrumMath.saturatedPoints(s.values) > 0)
                    Text("Raies saturées (sommets plats) : réduisez le temps de pose pour un étalonnage précis.",
                         color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = {
                val s = src ?: run { vm.say("Pas de spectre de lampe"); return@Button }
                val pk = SpectrumMath.findPeaks(s.values, 0.04, 6, 80).map { SpectrumMath.gaussPeak(s.values, it) }
                val r = LineCatalog.robustCalibration(pk, current, lines, order)
                if (r == null) {
                    vm.say("Identification automatique impossible : ajoutez quelques raies à la main")
                } else {
                    points = r.first.entries.map { it.key to it.value }
                    fit = r.second
                    vm.say("${points.size} raies identifiées, écart RMS " + fmt(r.second.rms, 3) + " nm")
                }
            }, modifier = Modifier.fillMaxWidth()) { Text("Identification automatique") }
            Text("Part de l'étalonnage actuel du Pi : il doit être juste à ±3 nm près. Sinon, ajoutez d'abord " +
                 "2 ou 3 raies sûres à la main, ajustez, puis relancez l'identification.",
                 style = MaterialTheme.typography.bodySmall)

            val sp = snapped()
            if (sp != null) {
                val predicted = SpectrumMath.polyval(model, sp)
                val near = lines.sortedBy { abs(it.nm - predicted) }.take(8)
                Text("Ajout manuel au pic du curseur : pixel " + fmt(sp, 2) + " (≈ " + fmt(predicted, 2) + " nm)",
                     style = MaterialTheme.typography.bodySmall)
                Dropdown("Raie du catalogue", near.map { it.nm to (fmt(it.nm, 3) + " nm " + it.label) },
                         manualNm ?: near.firstOrNull()?.nm, { manualNm = it })
                Button(onClick = {
                    val nm = manualNm ?: near.firstOrNull()?.nm ?: return@Button
                    val line = lines.first { it.nm == nm }
                    refit(points.filterNot { abs(it.first - sp) < 2 || it.second.nm == nm } + (sp to line))
                }, modifier = Modifier.fillMaxWidth()) { Text("Ajouter ce point") }
            } else {
                Text("Touchez une raie sur le graphique pour l'ajouter à la main.", style = MaterialTheme.typography.bodySmall)
            }
        }

        Section("Points (${points.size})") {
            val f = fit
            for ((i, pt) in points.withIndex()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val res = f?.let { pt.second.nm - SpectrumMath.polyval(it.coeffs, pt.first) }
                    Text("px " + fmt(pt.first, 2), Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                    Text(fmt(pt.second.nm, 3) + " " + pt.second.label, Modifier.weight(1.3f), style = MaterialTheme.typography.bodySmall)
                    Text(res?.let { (if (it >= 0) "+" else "") + fmt(it, 3) } ?: "", Modifier.weight(0.8f),
                         style = MaterialTheme.typography.bodySmall,
                         color = if (res != null && abs(res) > 0.1) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                    TextButton(onClick = { refit(points.filterIndexed { k, _ -> k != i }) }) { Text("✕") }
                }
            }
            if (points.isNotEmpty()) TextButton(onClick = { points = emptyList(); fit = null }) { Text("Tout effacer") }
        }

        fit?.let { f ->
            Section("Résultat") {
                val n = src?.values?.size ?: 3648
                val disp = SpectrumMath.polyval(f.coeffs, n / 2.0 + 0.5) - SpectrumMath.polyval(f.coeffs, n / 2.0 - 0.5)
                KV("Écart RMS", fmt(f.rms, 3) + " nm  (" + fmt(f.rms / abs(disp), 2) + " px)")
                KV("Dispersion au centre", fmt(disp, 4) + " nm/px")
                KV("Plage couverte", fmt(SpectrumMath.polyval(f.coeffs, 0.0), 1) + " – " +
                                     fmt(SpectrumMath.polyval(f.coeffs, n - 1.0), 1) + " nm")
                KV("Coefficients", f.coeffs.joinToString("  ") { String.format(java.util.Locale.ROOT, "%.6g", it) })
                Button(onClick = {
                    vm.saveCalibration(Calib(f.coeffs, points.map { it.first to it.second.nm }, f.rms))
                }, modifier = Modifier.fillMaxWidth()) { Text("Enregistrer sur le Pi") }
                Text("Le Pi l'applique à tous les affichages en nm et aux exports FITS.", style = MaterialTheme.typography.bodySmall)
            }
        }

        st?.calib?.let { c ->
            Section("Étalonnage actuel du Pi") {
                KV("Date", c.date?.take(16)?.replace('T', ' ') ?: "par défaut")
                KV("Points", c.points.size.toString())
                c.rms?.let { KV("Écart RMS", fmt(it, 3) + " nm") }
                KV("Plage", fmt(SpectrumMath.polyval(c.coeffs, 0.0), 1) + " – " + fmt(SpectrumMath.polyval(c.coeffs, 3647.0), 1) + " nm")
            }
        }
    }
}
