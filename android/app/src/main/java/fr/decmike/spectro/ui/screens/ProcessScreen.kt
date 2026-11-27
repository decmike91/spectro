@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package fr.decmike.spectro.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import fr.decmike.spectro.data.Spectrum
import fr.decmike.spectro.data.kindLabel
import fr.decmike.spectro.math.Combine
import fr.decmike.spectro.math.LineCatalog
import fr.decmike.spectro.math.SpectrumMath
import fr.decmike.spectro.ui.AppViewModel
import fr.decmike.spectro.ui.ChartMarker
import fr.decmike.spectro.ui.ChartSeries
import fr.decmike.spectro.ui.Chips
import fr.decmike.spectro.ui.Dropdown
import fr.decmike.spectro.ui.KV
import fr.decmike.spectro.ui.NumField
import fr.decmike.spectro.ui.Section
import fr.decmike.spectro.ui.SpectrumChart
import fr.decmike.spectro.ui.TextField1
import fr.decmike.spectro.ui.fmt
import fr.decmike.spectro.ui.theme.seriesColors
import fr.decmike.spectro.ui.toDoubleOr
import fr.decmike.spectro.ui.toIntOr
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/** Opérations proposées sur l'espace de travail. */
enum class Op(val label: String, val needsB: Boolean = false, val param: String? = null, val multi: Boolean = false) {
    SUB("A − B (soustraire un noir, un fond…)", needsB = true),
    ADD("A + B", needsB = true),
    DIV("A ÷ B (flat, réponse…)", needsB = true),
    MEAN("Moyenne des spectres cochés", multi = true),
    MEDIAN("Médiane des spectres cochés", multi = true),
    SUM("Somme des spectres cochés", multi = true),
    TRANS("Transmission A ÷ B en % (filtre)", needsB = true),
    ABSORB("Absorbance −log₁₀(A ÷ B)", needsB = true),
    MULK("A × k", param = "k"),
    OFFK("A + k", param = "k"),
    NORM_MAX("Normaliser au maximum"),
    NORM_REG("Normaliser sur la zone sélectionnée"),
    BOX("Lissage moyenne glissante", param = "largeur (px)"),
    SG("Lissage Savitzky-Golay", param = "fenêtre (px)"),
    CONT_DIV("Diviser par le continuum", param = "ordre du polynôme"),
    CONT_SUB("Soustraire le continuum", param = "ordre du polynôme"),
    RESPONSE("Corriger la réponse : A ÷ B × Planck(T)", needsB = true, param = "T de l'étoile B (K)"),
}

@Composable
fun ProcessScreen(vm: AppViewModel) {
    val ws by vm.workspace.collectAsState()
    val st by vm.status.collectAsState()
    val axisNm by vm.axisNm.collectAsState()
    val night by vm.nightMode.collectAsState()
    val colors = seriesColors(night)

    var visible by remember { mutableStateOf(setOf<Long>()) }
    var aUid by remember { mutableStateOf(-1L) }
    var bUid by remember { mutableStateOf(-1L) }
    var op by remember { mutableStateOf(Op.SUB) }
    var param by remember { mutableStateOf("") }
    var cursor by remember { mutableStateOf<Int?>(null) }
    var r0 by remember { mutableStateOf<Int?>(null) }
    var r1 by remember { mutableStateOf<Int?>(null) }
    var markers by remember { mutableStateOf(listOf<ChartMarker>()) }
    var measure by remember { mutableStateOf<List<Pair<String, String>>>(emptyList()) }
    var restIdx by remember { mutableStateOf(0) }
    var absorption by remember { mutableStateOf(true) }
    var renaming by remember { mutableStateOf<Spectrum?>(null) }

    val a = ws.firstOrNull { it.uid == aUid } ?: ws.lastOrNull()
    val b = ws.firstOrNull { it.uid == bUid }
    val coeffs = st?.calib?.coeffs
    val toNm: ((Double) -> Double)? = if (axisNm && coeffs != null) { p -> SpectrumMath.polyval(coeffs, p) } else null
    fun xAxis(n: Int): DoubleArray =
        if (coeffs != null) DoubleArray(n) { SpectrumMath.polyval(coeffs, it.toDouble()) } else DoubleArray(n) { it.toDouble() }

    fun compute() {
        val A = a ?: run { vm.say("Choisissez un spectre A"); return }
        try {
            val p = param
            val res: Pair<DoubleArray, String> = when (op) {
                Op.SUB, Op.ADD, Op.DIV, Op.TRANS, Op.ABSORB, Op.RESPONSE -> {
                    val B = b ?: run { vm.say("Choisissez un spectre B"); return }
                    when (op) {
                        Op.SUB -> SpectrumMath.subtract(A.values, B.values) to "${A.name} − ${B.name}"
                        Op.ADD -> SpectrumMath.add(A.values, B.values) to "${A.name} + ${B.name}"
                        Op.DIV -> SpectrumMath.divide(A.values, B.values) to "${A.name} ÷ ${B.name}"
                        Op.TRANS -> SpectrumMath.transmission(A.values, B.values) to "T% ${A.name}"
                        Op.ABSORB -> SpectrumMath.absorbance(A.values, B.values) to "Abs ${A.name}"
                        else -> {
                            if (coeffs == null) { vm.say("Étalonnage nécessaire"); return }
                            val t = p.toDoubleOr(9600.0)
                            val x = xAxis(A.values.size)
                            val q = SpectrumMath.divide(A.values, B.values)
                            val pl = DoubleArray(x.size) { SpectrumMath.planck(x[it], t) }
                            SpectrumMath.normalizeMax(SpectrumMath.multiply(q, pl)) to "${A.name} corrigé"
                        }
                    }
                }
                Op.MEAN, Op.MEDIAN, Op.SUM -> {
                    val list = ws.filter { it.uid in visible }
                    if (list.size < 2) { vm.say("Cochez au moins 2 spectres"); return }
                    val mode = when (op) { Op.MEAN -> Combine.MEAN; Op.MEDIAN -> Combine.MEDIAN; else -> Combine.SUM }
                    SpectrumMath.combine(list.map { it.values }, mode) to "${mode.label} (${list.size})"
                }
                Op.MULK -> SpectrumMath.scale(A.values, p.toDoubleOr(1.0)) to "${A.name} × $p"
                Op.OFFK -> SpectrumMath.offset(A.values, p.toDoubleOr(0.0)) to "${A.name} + $p"
                Op.NORM_MAX -> SpectrumMath.normalizeMax(A.values) to "${A.name} norm."
                Op.NORM_REG -> {
                    val i0 = r0; val i1 = r1
                    if (i0 == null || i1 == null) { vm.say("Placez les deux bornes de la zone"); return }
                    SpectrumMath.normalizeRegion(A.values, i0, i1) to "${A.name} norm."
                }
                Op.BOX -> SpectrumMath.boxcar(A.values, p.toIntOr(5)) to "${A.name} lissé"
                Op.SG -> SpectrumMath.savitzkyGolay(A.values, p.toIntOr(11), 2) to "${A.name} lissé SG"
                Op.CONT_DIV, Op.CONT_SUB -> {
                    val x = xAxis(A.values.size)
                    val c = SpectrumMath.continuum(x, A.values, p.toIntOr(3).coerceIn(1, 8))
                    if (op == Op.CONT_DIV) SpectrumMath.divide(A.values, c) to "${A.name} / continuum"
                    else SpectrumMath.subtract(A.values, c) to "${A.name} − continuum"
                }
            }
            val (vals, name) = res
            val multi = op.multi
            val frames = if (multi) ws.filter { it.uid in visible }.sumOf { it.nFrames } else A.nFrames
            val r = Spectrum(vm.newUid(), name, "result", vals, AppViewModel.now(), A.tintUs, frames,
                             history = A.history + (op.label + if (op.param != null) " = $p" else ""))
            vm.addToWorkspace(r)
            aUid = r.uid
            visible = visible + r.uid
        } catch (e: Exception) {
            vm.say("Calcul impossible : ${e.message}")
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        val shown = ws.filter { it.uid in visible || it.uid == a?.uid }
        val series = shown.mapIndexed { i, s -> ChartSeries(s.values, colors[i % colors.size], s.name) }
            .sortedByDescending { it.label == a?.name }      // A en premier (lu par le curseur)
        val region = if (r0 != null && r1 != null) Pair(r0!!, r1!!) else null
        SpectrumChart(series, Modifier.padding(4.dp), height = 280.dp, toNm = toNm, markers = markers,
                      cursor = cursor, onCursor = { cursor = it }, region = region)

        Section("Espace de travail (${ws.size})") {
            if (ws.isEmpty()) Text("Chargez des spectres depuis « Spectres » ou figez le direct.",
                                   style = MaterialTheme.typography.bodySmall)
            for (s in ws) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = s.uid in visible, onCheckedChange = {
                        visible = if (it) visible + s.uid else visible - s.uid
                    })
                    Column(Modifier.weight(1f).clickable { aUid = s.uid }) {
                        Text((if (s.uid == a?.uid) "A · " else if (s.uid == b?.uid) "B · " else "") + s.name,
                             fontWeight = if (s.uid == a?.uid) FontWeight.Bold else FontWeight.Normal)
                        Text(kindLabel(s.kind) + (if (s.piId != null) " · sur le Pi" else " · local") +
                             (s.history.lastOrNull()?.let { " · $it" } ?: ""), style = MaterialTheme.typography.bodySmall)
                    }
                    var menu by remember { mutableStateOf(false) }
                    Box {
                        IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, "Actions") }
                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                            DropdownMenuItem(text = { Text("Choisir comme A") }, onClick = { menu = false; aUid = s.uid })
                            DropdownMenuItem(text = { Text("Choisir comme B") }, onClick = { menu = false; bUid = s.uid })
                            DropdownMenuItem(text = { Text("Enregistrer sur le Pi") }, onClick = { menu = false; vm.saveToPi(s) })
                            DropdownMenuItem(text = { Text("Partager en CSV") }, onClick = { menu = false; vm.exportLocal(s, "csv") })
                            DropdownMenuItem(text = { Text("Partager en FITS") }, onClick = { menu = false; vm.exportLocal(s, "fits") })
                            DropdownMenuItem(text = { Text("Renommer") }, onClick = { menu = false; renaming = s })
                            DropdownMenuItem(text = { Text("Retirer") }, onClick = { menu = false; vm.removeFromWorkspace(s.uid) })
                        }
                    }
                }
            }
        }

        Section("Opérations") {
            Dropdown("Opération", Op.entries.map { it to it.label }, op, { op = it; param = "" })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Dropdown("Spectre A", ws.map { it.uid to it.name }, a?.uid ?: -1L, { aUid = it }, Modifier.weight(1f))
                if (op.needsB) Dropdown("Spectre B", ws.map { it.uid to it.name }, bUid, { bUid = it }, Modifier.weight(1f))
            }
            op.param?.let { NumField(it, param, { v -> param = v }, Modifier.fillMaxWidth()) }
            if (op.multi) Text("Utilise les spectres cochés ci-dessus.", style = MaterialTheme.typography.bodySmall)
            Button(onClick = { compute() }, modifier = Modifier.fillMaxWidth()) { Text("Calculer") }
        }

        Section("Analyse de A") {
            Text("Touchez le graphique pour placer le curseur, puis fixez les bornes de la zone.",
                 style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { r0 = cursor }, modifier = Modifier.weight(1f)) { Text("Borne 1") }
                OutlinedButton(onClick = { r1 = cursor }, modifier = Modifier.weight(1f)) { Text("Borne 2") }
                OutlinedButton(onClick = { r0 = null; r1 = null; measure = emptyList() }) { Text("Effacer") }
            }
            Dropdown("Raie de référence (vitesse radiale)", LineCatalog.ASTRO.indices.map {
                it to (LineCatalog.ASTRO[it].label + " " + fmt(LineCatalog.ASTRO[it].nm, 2) + " nm")
            }, restIdx, { restIdx = it })
            Button(onClick = {
                val A = a; val i0 = r0; val i1 = r1
                if (A == null || i0 == null || i1 == null) { vm.say("Spectre A et zone nécessaires"); return@Button }
                val x = xAxis(A.values.size)
                val m = SpectrumMath.measureLine(x, A.values, i0, i1)
                if (m == null) { vm.say("Zone trop étroite"); return@Button }
                val u = if (coeffs != null) "nm" else "px"
                val out = ArrayList<Pair<String, String>>()
                out += "Type" to if (m.emission) "émission" else "absorption"
                out += "Centre" to fmt(m.center, 3) + " " + u
                out += "FWHM" to fmt(m.fwhm, 3) + " " + u
                if (coeffs != null && m.fwhm > 0) out += "Pouvoir de résolution λ/Δλ" to fmt(m.center / m.fwhm, 0)
                out += (if (m.emission) "Hauteur" else "Profondeur") to fmt(abs(m.depth), 1) + " (" +
                       fmt(100 * abs(m.depth) / max(1e-9, abs(m.baseline)), 1) + " % du fond)"
                out += "Flux intégré" to fmt(m.flux, 1)
                out += "Largeur équivalente" to if (coeffs != null) fmt(m.ew * 10, 2) + " Å" else fmt(m.ew, 2) + " px"
                out += "S/B de la zone" to fmt(SpectrumMath.snr(A.values, min(i0, i1), max(i0, i1)), 0)
                if (coeffs != null) {
                    val rest = LineCatalog.ASTRO[restIdx]
                    out += "Vitesse radiale / ${rest.label}" to fmt(SpectrumMath.radialVelocity(m.center, rest.nm), 1) + " km/s"
                }
                measure = out
            }, modifier = Modifier.fillMaxWidth()) { Text("Mesurer la raie dans la zone") }
            for ((k, v) in measure) KV(k, v)
            if (measure.any { it.first.startsWith("Vitesse") })
                Text("Vitesse non corrigée du mouvement de la Terre (correction héliocentrique à appliquer).",
                     style = MaterialTheme.typography.bodySmall)

            Chips(listOf(true to "Raies d'absorption", false to "Raies d'émission"), absorption) { absorption = it }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val A = a ?: return@Button
                    val pk = SpectrumMath.findPeaks(A.values, 0.15, 10, 25, absorption)
                    val cat = if (A.kind == "lamp") LineCatalog.LAMPS.values.flatten() else LineCatalog.ASTRO
                    markers = pk.map { i ->
                        val pos = SpectrumMath.refinePeak(if (absorption) SpectrumMath.scale(A.values, -1.0) else A.values, i)
                        val label = if (coeffs != null) {
                            val nm = SpectrumMath.polyval(coeffs, pos)
                            fmt(nm, 1) + (LineCatalog.nearest(nm, cat, 1.0)?.let { " " + it.label } ?: "")
                        } else fmt(pos, 1)
                        ChartMarker(pos, label, colors[1])
                    }
                }, modifier = Modifier.weight(1f)) { Text("Détecter les raies") }
                OutlinedButton(onClick = {
                    markers = if (coeffs == null) emptyList() else LineCatalog.ASTRO.mapNotNull { l ->
                        val n = a?.values?.size ?: return@mapNotNull null
                        val idx = fr.decmike.spectro.ui.invert({ p -> SpectrumMath.polyval(coeffs, p) }, l.nm, 0.0, n - 1.0)
                        if (idx <= 0.5 || idx >= n - 1.5) null else ChartMarker(idx, l.label, colors[2])
                    }
                }, modifier = Modifier.weight(1f)) { Text("Raies de référence") }
            }
            if (markers.isNotEmpty()) TextButton(onClick = { markers = emptyList() }) { Text("Effacer les repères") }
        }
    }

    renaming?.let { s ->
        var newName by remember(s.uid) { mutableStateOf(s.name) }
        AlertDialog(
            onDismissRequest = { renaming = null },
            title = { Text("Renommer") },
            text = { TextField1("Nom", newName, { newName = it }) },
            confirmButton = { TextButton(onClick = { vm.renameInWorkspace(s.uid, newName); renaming = null }) { Text("OK") } },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text("Annuler") } },
        )
    }
}
