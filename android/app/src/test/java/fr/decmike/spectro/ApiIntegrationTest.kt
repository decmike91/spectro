package fr.decmike.spectro

import fr.decmike.spectro.data.Calib
import fr.decmike.spectro.data.SpectroApi
import fr.decmike.spectro.data.Spectrum
import fr.decmike.spectro.data.parseFrame
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Dialogue réel avec le serveur du Pi lancé en simulateur (logiciel/serveur/spectro_server.py --sim).
 * Exécuté par GitHub Actions ; ignoré si SPECTRO_TEST_URL n'est pas défini.
 */
class ApiIntegrationTest {
    private val url: String? = System.getenv("SPECTRO_TEST_URL")

    @Test fun fullWorkflow() = runBlocking {
        assumeTrue("serveur de test absent", !url.isNullOrBlank())
        val api = SpectroApi(url!!)

        val st = api.status()
        assertTrue(st.sim)
        assertEquals(20000L, api.config(tintUs = 20000, averages = 2).tintUs)

        // direct par WebSocket
        val got = CountDownLatch(3)
        var n = 0
        val ws = api.openSocket(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                val o = JSONObject(text)
                if (o.getString("type") == "frame") {
                    n = parseFrame(o).values.size
                    got.countDown()
                }
            }
            override fun onOpen(webSocket: WebSocket, response: Response) {}
        })
        api.live(true, null)
        assertTrue("pas de spectre en direct", got.await(15, TimeUnit.SECONDS))
        assertEquals(3648, n)
        api.live(false, null)
        delay(500)

        // séquence de noirs puis séquence soustraite
        api.startSequence("noir_test", "dark", 3, 20000, 1, 0.0, "median", null, false)
        waitIdle(api)
        val dark = api.list().first { it.name == "noir_test" }
        assertEquals("dark", dark.kind)
        api.startSequence("lampe_test", "lamp", 4, 20000, 2, 0.0, "mean", dark.id, true)
        waitIdle(api)
        val lib = api.list()
        assertEquals(5, lib.count { it.name.startsWith("lampe_test") })   // 4 poses + moyenne

        // lecture, enregistrement d'un résultat, export, étalonnage
        val lamp = api.get(lib.first { it.name == "lampe_test" }.id, 1)
        assertEquals(3648, lamp.values.size)
        val id = api.save(Spectrum(2, "resultat_test", "result", DoubleArray(3648) { it * 0.5 }, tintUs = 20000))
        assertEquals(1823.5, api.get(id, 3).values[3647], 1e-6)
        assertTrue(String(api.download(id, "fits"), Charsets.US_ASCII).startsWith("SIMPLE"))
        assertTrue(String(api.download(id, "csv")).contains("pixel;"))
        val c = api.putCalib(Calib(doubleArrayOf(350.0, 0.135, -2e-6), listOf(100.0 to 363.48), 0.02))
        assertEquals(0.135, c.coeffs[1], 1e-12)
        api.rename(id, "renomme")
        assertTrue(api.list().any { it.name == "renomme" })
        api.delete(id)
        assertTrue(api.list().none { it.id == id })
        ws.close(1000, null)
    }

    private suspend fun waitIdle(api: SpectroApi) {
        delay(300)
        repeat(100) {
            if (api.status().job == null) return
            delay(200)
        }
        throw AssertionError("séquence trop longue")
    }
}
