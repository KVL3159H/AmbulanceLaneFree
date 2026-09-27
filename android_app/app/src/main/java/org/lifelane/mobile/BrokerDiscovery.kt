package org.lifelane.mobile

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Zero-Configuration Auto-Discovery for LifeLane Broker on Android.
 *
 * Automatically detects the PC/laptop running the LifeLane desktop or web software
 * on any Wi-Fi network, mobile hotspot, or office LAN:
 * 1. Listens for UDP beacons on port 18830.
 * 2. Broadcasts UDP search queries on port 18830.
 * 3. Quick-probes common subnet IPs on port 1883 if UDP broadcast is isolated by the router.
 */
object BrokerDiscovery {
    private const val TAG = "LifeLaneDiscovery"
    const val DISCOVERY_PORT = 18830

    @Volatile
    var discoveredHost: String? = null
        private set

    @Volatile
    var isDiscovering = false
        private set

    private var discoveryJob: Job? = null

    fun startAutoDiscovery(
        context: Context,
        scope: CoroutineScope,
        onDiscovered: (host: String, port: Int) -> Unit,
    ) {
        if (isDiscovering) return
        isDiscovering = true

        discoveryJob = scope.launch(Dispatchers.IO) {
            val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            val multicastLock = wifiManager?.createMulticastLock("LifeLaneDiscoveryLock")?.apply {
                setReferenceCounted(true)
                acquire()
            }

            try {
                var socket: DatagramSocket? = null
                try {
                    socket = DatagramSocket(null).apply {
                        reuseAddress = true
                        broadcast = true
                        soTimeout = 2000
                        bind(InetSocketAddress(DISCOVERY_PORT))
                    }
                } catch (bindErr: Exception) {
                    Log.d(TAG, "Could not bind port $DISCOVERY_PORT, creating unbound socket: $bindErr")
                    socket = DatagramSocket().apply {
                        broadcast = true
                        soTimeout = 2000
                    }
                }

                // Send initial search probe to global broadcast
                val searchProbe = JSONObject().put("query", "lifelane_discover").toString().toByteArray()
                try {
                    socket.send(DatagramPacket(searchProbe, searchProbe.size, InetAddress.getByName("255.255.255.255"), DISCOVERY_PORT))
                } catch (e: Exception) {
                    Log.d(TAG, "Initial search probe failed: $e")
                }

                val buffer = ByteArray(2048)
                val packet = DatagramPacket(buffer, buffer.size)

                var attempts = 0
                while (isActive && discoveredHost == null && attempts < 15) {
                    attempts++
                    // Try receiving UDP beacon
                    try {
                        socket.receive(packet)
                        val text = String(packet.data, 0, packet.length)
                        val json = JSONObject(text)
                        if (json.optString("service") == "lifelane_broker") {
                            val host = json.optString("ip", packet.address.hostAddress.orEmpty())
                            val port = json.optInt("mqtt_port", 1883)
                            if (host.isNotBlank()) {
                                discoveredHost = host
                                Log.i(TAG, "Discovered LifeLane PC via UDP Beacon at $host:$port")
                                withContext(Dispatchers.Main) { onDiscovered(host, port) }
                                break
                            }
                        }
                    } catch (_: Exception) {
                        // Socket timeout or receive failure — fallback to active subnet probe
                    }

                    // Resend search probe periodically
                    if (attempts % 2 == 0) {
                        try {
                            socket.send(DatagramPacket(searchProbe, searchProbe.size, InetAddress.getByName("255.255.255.255"), DISCOVERY_PORT))
                        } catch (_: Exception) {}
                    }

                    // On 3rd attempt, probe common local Wi-Fi IPs if UDP broadcast is isolated by router
                    if (attempts == 3 && discoveredHost == null) {
                        probeLocalSubnet(wifiManager, onDiscovered)
                    }

                    delay(1000)
                }

                socket.close()
            } finally {
                try {
                    multicastLock?.release()
                } catch (_: Exception) {}
                isDiscovering = false
            }
        }
    }

    fun stop() {
        discoveryJob?.cancel()
        discoveryJob = null
        isDiscovering = false
    }

    /**
     * Fallback subnet sweep for routers that filter UDP broadcast packets between wireless clients.
     */
    private suspend fun probeLocalSubnet(
        wifiManager: WifiManager?,
        onDiscovered: (host: String, port: Int) -> Unit,
    ) = withContext(Dispatchers.IO) {
        val ipInt = wifiManager?.connectionInfo?.ipAddress ?: return@withContext
        if (ipInt == 0) return@withContext

        val b0 = ipInt and 0xff
        val b1 = (ipInt shr 8) and 0xff
        val b2 = (ipInt shr 16) and 0xff
        val phoneIp = "$b0.$b1.$b2.${(ipInt shr 24) and 0xff}"
        val subnetPrefix = "$b0.$b1.$b2."

        Log.d(TAG, "Probing subnet $subnetPrefix* for PC on port 1883 (Phone IP is $phoneIp)")

        // Check common target host IPs first: .1 (gateway), .208, and nearby hosts
        val priorityTargets = mutableListOf<String>()
        priorityTargets.add("${subnetPrefix}1")
        priorityTargets.add("${subnetPrefix}208")
        priorityTargets.add("${subnetPrefix}100")
        priorityTargets.add("${subnetPrefix}101")
        for (i in 2..20) priorityTargets.add("$subnetPrefix$i")

        for (target in priorityTargets.distinct()) {
            if (target == phoneIp) continue
            try {
                Socket().use { s ->
                    s.connect(InetSocketAddress(target, 1883), 150)
                    discoveredHost = target
                    Log.i(TAG, "Subnet probe found active broker at $target:1883")
                    withContext(Dispatchers.Main) { onDiscovered(target, 1883) }
                    return@withContext
                }
            } catch (_: Exception) {}
        }
    }
}
