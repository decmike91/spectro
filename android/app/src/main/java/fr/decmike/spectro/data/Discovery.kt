package fr.decmike.spectro.data

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo

/**
 * Recherche du serveur sur le réseau local (mDNS / DNS-SD, service « _spectro._tcp »
 * annoncé par avahi sur le Pi Zero).
 */
class Discovery(context: Context, private val onFound: (name: String, hostPort: String) -> Unit) {
    private val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private var listener: NsdManager.DiscoveryListener? = null

    fun start() {
        stop()
        val l = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onServiceLost(serviceInfo: NsdServiceInfo) {}
            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                @Suppress("DEPRECATION")
                nsd.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {}
                    override fun onServiceResolved(info: NsdServiceInfo) {
                        @Suppress("DEPRECATION")
                        val host = info.host?.hostAddress ?: return
                        onFound(info.serviceName, "$host:${info.port}")
                    }
                })
            }
        }
        listener = l
        try {
            nsd.discoverServices("_spectro._tcp.", NsdManager.PROTOCOL_DNS_SD, l)
        } catch (e: Exception) {
            listener = null
        }
    }

    fun stop() {
        listener?.let { try { nsd.stopServiceDiscovery(it) } catch (_: Exception) {} }
        listener = null
    }
}
