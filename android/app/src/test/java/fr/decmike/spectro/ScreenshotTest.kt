package fr.decmike.spectro

import android.app.Application
import android.content.Context
import android.graphics.Bitmap
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ApplicationProvider
import fr.decmike.spectro.ui.AppViewModel
import fr.decmike.spectro.ui.Conn
import fr.decmike.spectro.ui.Tab
import fr.decmike.spectro.ui.theme.SpectroTheme
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import java.io.FileOutputStream

/**
 * Affiche chaque écran, connecté au serveur du Pi lancé en simulateur, et enregistre une capture
 * dans app/build/captures (publiées par GitHub Actions). Ignoré sans SPECTRO_TEST_URL.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w400dp-h860dp-xhdpi")
class ScreenshotTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun shot(name: String, night: Boolean = false) {
        rule.waitForIdle()
        val dir = File("build/captures").apply { mkdirs() }
        val view = rule.activity.window.decorView
        val bmp = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(android.graphics.Canvas(bmp))
        FileOutputStream(File(dir, (if (night) "nuit_" else "") + "$name.png")).use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    @Test fun allScreens() {
        val url = System.getenv("SPECTRO_TEST_URL")
        assumeTrue("serveur de test absent", !url.isNullOrBlank())
        val app = ApplicationProvider.getApplicationContext<Application>()
        app.getSharedPreferences("spectro", Context.MODE_PRIVATE).edit().putString("host", url).commit()
        val vm = AppViewModel(app)
        rule.setContent {
            val n by vm.nightMode.collectAsState()
            SpectroTheme(n) { AppRoot(vm) }
        }
        rule.waitUntil(20_000) { vm.conn.value == Conn.CONNECTED }

        // Direct : un spectre puis arrêt (écran figé pour la capture)
        vm.setConfig(tintUs = 20_000, averages = 2)
        vm.setLive(true, null)
        rule.waitUntil(20_000) { vm.live.value != null }
        vm.setLive(false, null)
        rule.waitUntil(20_000) { vm.status.value?.live == false }
        Thread.sleep(300)
        shot("1_direct")

        // Séquences : une série de noirs, puis une séquence longue capturée en cours
        vm.startSequence("noirs", "dark", 3, 20_000, 1, 0.0, "median", null, false)
        rule.waitUntil(20_000) { vm.status.value?.job != null }
        rule.waitUntil(30_000) { vm.status.value?.job == null }
        vm.startSequence("vega", "light", 40, 20_000, 1, 0.5, "mean", null, false)
        vm.tab.value = Tab.SEQ
        rule.waitUntil(20_000) { (vm.status.value?.job?.index ?: 0) >= 2 }
        shot("2_sequences")
        vm.stopSequence()
        rule.waitUntil(30_000) { vm.status.value?.job == null }

        // Bibliothèque
        vm.startSequence("lampe HgAr", "lamp", 3, 20_000, 2, 0.0, "mean", null, false)
        rule.waitUntil(20_000) { vm.status.value?.job != null }
        rule.waitUntil(30_000) { vm.status.value?.job == null }
        vm.refreshLibrary()
        rule.waitUntil(20_000) { vm.library.value.any { it.name == "lampe HgAr" } }
        vm.tab.value = Tab.LIB
        shot("3_spectres")

        // Traitement : lampe + noir dans l'espace de travail, détection des raies
        val lib = vm.library.value
        vm.loadToWorkspace(listOf(lib.first { it.name == "noirs" }.id, lib.first { it.name == "lampe HgAr" }.id))
        rule.waitUntil(20_000) { vm.workspace.value.size == 2 }
        vm.tab.value = Tab.PROC
        rule.waitForIdle()
        rule.onNodeWithText("Détecter les raies").performScrollTo().performClick()
        rule.onNodeWithText("Raies d'émission").performScrollTo().performClick()
        rule.onNodeWithText("Détecter les raies").performScrollTo().performClick()
        shot("4_traitement")

        // Étalonnage : lampe Hg + Ar, identification automatique
        vm.tab.value = Tab.CALIB
        rule.waitForIdle()
        rule.onNodeWithText("Néon").performClick()
        rule.onNodeWithText("Mercure + Argon").performClick()
        rule.onNodeWithText("Identification automatique").performScrollTo().performClick()
        shot("5_etalonnage")

        // Mode nuit
        vm.setNight(true)
        vm.tab.value = Tab.LIVE
        shot("6_direct", night = true)
    }
}
