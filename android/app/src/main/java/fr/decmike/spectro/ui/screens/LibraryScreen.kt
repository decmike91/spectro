@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package fr.decmike.spectro.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import fr.decmike.spectro.data.KINDS
import fr.decmike.spectro.data.SpecMeta
import fr.decmike.spectro.data.kindLabel
import fr.decmike.spectro.ui.AppViewModel
import fr.decmike.spectro.ui.Chips
import fr.decmike.spectro.ui.TextField1
import fr.decmike.spectro.ui.fmt

/** Bibliothèque des spectres enregistrés sur le Pi. */
@Composable
fun LibraryScreen(vm: AppViewModel) {
    val lib by vm.library.collectAsState()
    var filter by remember { mutableStateOf<String?>(null) }
    var selected by remember { mutableStateOf(setOf<String>()) }
    var confirmDelete by remember { mutableStateOf<SpecMeta?>(null) }
    var renaming by remember { mutableStateOf<SpecMeta?>(null) }

    val items = lib.filter { filter == null || it.kind == filter }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) {
                Chips(listOf<Pair<String?, String>>(null to "Tous") + KINDS.map { it to kindLabel(it) }, filter) { filter = it }
            }
            IconButton(onClick = { vm.refreshLibrary() }) { Icon(Icons.Filled.Refresh, "Actualiser") }
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.loadToWorkspace(selected.toList()); selected = emptySet() },
                   enabled = selected.isNotEmpty(), modifier = Modifier.weight(1f)) {
                Text("Charger dans l'espace de travail (${selected.size})")
            }
            TextButton(onClick = { selected = if (selected.isEmpty()) items.map { it.id }.toSet() else emptySet() }) {
                Text(if (selected.isEmpty()) "Tout" else "Aucun")
            }
        }
        LazyColumn(Modifier.fillMaxSize()) {
            items(items, key = { it.id }) { m ->
                Card(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 3.dp)) {
                    Row(Modifier.padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = m.id in selected, onCheckedChange = {
                            selected = if (it) selected + m.id else selected - m.id
                        })
                        Column(Modifier.weight(1f)) {
                            Text(m.name, fontWeight = FontWeight.Bold)
                            Text(kindLabel(m.kind) + " · " + m.date.take(16).replace('T', ' ') + " · " +
                                 fmt(m.tintUs / 1000.0, 1) + " ms × " + m.nFrames +
                                 (m.combine?.let { " ($it)" } ?: "") + if (m.saturated) " · saturé" else "",
                                 style = MaterialTheme.typography.bodySmall)
                        }
                        var menu by remember { mutableStateOf(false) }
                        Box {
                            IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, "Actions") }
                            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                                DropdownMenuItem(text = { Text("Charger") }, onClick = { menu = false; vm.loadToWorkspace(listOf(m.id)) })
                                DropdownMenuItem(text = { Text("Partager en CSV") }, onClick = { menu = false; vm.exportFromPi(m.id, "csv") })
                                DropdownMenuItem(text = { Text("Partager en FITS") }, onClick = { menu = false; vm.exportFromPi(m.id, "fits") })
                                DropdownMenuItem(text = { Text("Renommer") }, onClick = { menu = false; renaming = m })
                                DropdownMenuItem(text = { Text("Supprimer") }, onClick = { menu = false; confirmDelete = m })
                            }
                        }
                    }
                }
            }
            if (items.isEmpty()) item {
                Text("Aucun spectre sur le Pi.", Modifier.padding(16.dp))
            }
        }
    }

    confirmDelete?.let { m ->
        AlertDialog(
            onDismissRequest = { confirmDelete = null },
            title = { Text("Supprimer « ${m.name} » ?") },
            text = { Text("Le fichier sera effacé du Pi.") },
            confirmButton = { TextButton(onClick = { vm.deleteOnPi(m.id); confirmDelete = null }) { Text("Supprimer") } },
            dismissButton = { TextButton(onClick = { confirmDelete = null }) { Text("Annuler") } },
        )
    }
    renaming?.let { m ->
        var newName by remember(m.id) { mutableStateOf(m.name) }
        AlertDialog(
            onDismissRequest = { renaming = null },
            title = { Text("Renommer") },
            text = { TextField1("Nom", newName, { newName = it }) },
            confirmButton = { TextButton(onClick = { vm.renameOnPi(m.id, newName); renaming = null }) { Text("OK") } },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text("Annuler") } },
        )
    }
}
