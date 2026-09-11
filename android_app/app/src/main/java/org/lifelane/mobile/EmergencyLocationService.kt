package org.lifelane.mobile

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.os.Build
import android.os.IBinder
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationAvailability
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import java.time.Instant
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import org.json.JSONObject

class EmergencyLocationService : Service() {
    private val fused by lazy { LocationServices.getFusedLocationProviderClient(this) }
    private var mqtt: MqttGateway? = null
    private val sequence = AtomicLong(100)
    private lateinit var ambulanceId: String
    private lateinit var tripId: String
    private lateinit var priority: String
    private lateinit var condition: String
    private lateinit var destination: String
    private var destinationLat: Double = 9.456500
    private var destinationLon: Double = 77.553500
    private var junctionLat: Double = JUNCTION_LAT
    private var junctionLon: Double = JUNCTION_LON
    private var junctionInitialized: Boolean = false

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            val location = result.lastLocation
            if (location == null) TripStatusRepository.update { it.copy(gpsStatus = "Waiting for GPS signal") }
            else publishLocation(location)
        }

        override fun onLocationAvailability(availability: LocationAvailability) {
            if (!availability.isLocationAvailable) {
                TripStatusRepository.update { current -> current.copy(gpsStatus = "GPS signal unavailable") }
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startEmergency(intent)
            ACTION_COMPLETE -> stopEmergency(cancelled = false)
            ACTION_CANCEL -> stopEmergency(cancelled = true)
            ACTION_RETRY -> retryConnections()
        }
        return START_NOT_STICKY
    }

    private fun startEmergency(intent: Intent) {
        ambulanceId = intent.getStringExtra(EXTRA_AMBULANCE_ID) ?: return stopSelf()
        tripId = intent.getStringExtra(EXTRA_TRIP_ID) ?: return stopSelf()
        priority = intent.getStringExtra(EXTRA_PRIORITY) ?: "RED"
        condition = intent.getStringExtra(EXTRA_CONDITION) ?: "OTHER"
        destination = intent.getStringExtra(EXTRA_DESTINATION) ?: ""
        destinationLat = intent.getDoubleExtra(EXTRA_DEST_LAT, 9.456500)
        destinationLon = intent.getDoubleExtra(EXTRA_DEST_LON, 77.553500)
        junctionLat = intent.getDoubleExtra(EXTRA_JUNC_LAT, JUNCTION_LAT)
        junctionLon = intent.getDoubleExtra(EXTRA_JUNC_LON, JUNCTION_LON)
        junctionInitialized = false
        createNotificationChannel()
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_lifelane)
            .setContentTitle("LifeLane emergency trip active")
            .setContentText("Transmitting GPS for $ambulanceId")
            .setContentIntent(openApp)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else startForeground(NOTIFICATION_ID, notification)

        mqtt = MqttGateway(
            ambulanceId,
            { state -> TripStatusRepository.update { it.copy(mqttStatus = state) } },
            { json ->
                val selected = json.optString("selectedAmbulance", "")
                val junctionRequest = json.optString("requestStatus", "Waiting")
                TripStatusRepository.update {
                    it.copy(
                        signalStatus = json.optString("signalState", "Unknown"),
                        requestStatus = when {
                            selected == ambulanceId -> junctionRequest.ifBlank { "Selected" }
                            selected.isNotBlank() -> "Waiting in queue"
                            else -> junctionRequest
                        },
                    )
                }
            },
        ).also { it.connect() }
        mqtt?.publish(
            "lifelane/ambulance/$ambulanceId/emergency",
            JSONObject().apply {
                put("schemaVersion", 1); put("sequenceNumber", sequence.incrementAndGet())
                put("ambulanceId", ambulanceId); put("tripId", tripId); put("emergencyActive", true)
                put("timestamp", Instant.now().toString())
            }.toString(),
        )
        requestGpsUpdates()
    }

    private fun requestGpsUpdates() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            TripStatusRepository.update { it.copy(gpsStatus = "Location permission denied", emergencyActive = true) }
            return
        }
        fused.removeLocationUpdates(callback)
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1_500L)
            .setMinUpdateIntervalMillis(1_000L)
            .build()
        fused.requestLocationUpdates(request, callback, mainLooper)
        TripStatusRepository.update { it.copy(gpsStatus = "Acquiring GPS", emergencyActive = true) }
    }

    private fun publishLocation(location: Location) {
        if (!::ambulanceId.isInitialized) return
        if (!validLocation(location)) {
            val status = if (!location.hasAccuracy()) "GPS accuracy unavailable" else "GPS inaccurate (${location.accuracy.toInt()} m)"
            TripStatusRepository.update { it.copy(gpsStatus = status, accuracyMetres = if (location.hasAccuracy()) location.accuracy else it.accuracyMetres) }
            return
        }
        if (!junctionInitialized) {
            val distToDemo = distanceMetres(location.latitude, location.longitude, JUNCTION_LAT, JUNCTION_LON)
            if (distToDemo <= 20_000.0) {
                junctionLat = JUNCTION_LAT
                junctionLon = JUNCTION_LON
            } else {
                junctionLat = (location.latitude + destinationLat) / 2.0
                junctionLon = (location.longitude + destinationLon) / 2.0
            }
            junctionInitialized = true
        }
        val distance = distanceMetres(location.latitude, location.longitude, junctionLat, junctionLon)
        val relativeBearing = bearing(junctionLat, junctionLon, location.latitude, location.longitude)
        val approach = when {
            relativeBearing >= 315 || relativeBearing < 45 -> "NORTH"
            relativeBearing < 135 -> "EAST"
            relativeBearing < 225 -> "SOUTH"
            else -> "WEST"
        }
        val json = JSONObject().apply {
            put("schemaVersion", 1)
            put("sequenceNumber", sequence.incrementAndGet())
            put("ambulanceId", ambulanceId)
            put("tripId", tripId)
            put("latitude", location.latitude)
            put("longitude", location.longitude)
            put("accuracyMetres", location.accuracy.toDouble())
            put("speedMps", location.speed.coerceAtLeast(0f).toDouble())
            put("headingDegrees", if (location.hasBearing()) location.bearing.toDouble() else 0.0)
            put("patientPriority", priority)
            put("patientCondition", condition)
            put("destinationHospital", destination)
            put("emergencyActive", true)
            put("timestamp", Instant.now().toString())
        }
        mqtt?.publish("lifelane/ambulance/$ambulanceId/telemetry", json.toString())
        TripStatusRepository.update {
            it.copy(
                latitude = location.latitude, longitude = location.longitude,
                accuracyMetres = location.accuracy, speedMps = location.speed.coerceAtLeast(0f),
                headingDegrees = if (location.hasBearing()) location.bearing else 0f,
                gpsStatus = "Live", distanceMetres = distance, detectedApproach = approach,
                requestStatus = if (distance <= 300) "Sent" else "Outside activation radius",
            )
        }
    }

    private fun validLocation(location: Location): Boolean =
        location.latitude in -90.0..90.0 && location.longitude in -180.0..180.0 &&
            location.hasAccuracy() && location.accuracy in 0f..100f

    private fun retryConnections() {
        if (!::ambulanceId.isInitialized) return
        TripStatusRepository.update { it.copy(mqttStatus = "Connecting", gpsStatus = "Acquiring GPS") }
        mqtt?.reconnect()
        requestGpsUpdates()
    }

    private fun stopEmergency(cancelled: Boolean) {
        fused.removeLocationUpdates(callback)
        if (::ambulanceId.isInitialized) {
            val topic = if (cancelled) "lifelane/ambulance/$ambulanceId/cancel" else "lifelane/ambulance/$ambulanceId/emergency"
            mqtt?.publish(topic, JSONObject().apply {
                put("schemaVersion", 1); put("sequenceNumber", sequence.incrementAndGet())
                put("ambulanceId", ambulanceId); put("tripId", tripId)
                put("emergencyActive", false); put("timestamp", Instant.now().toString())
            }.toString())
        }
        mqtt?.disconnect()
        TripStatusRepository.update { it.copy(emergencyActive = false, gpsStatus = "Stopped", mqttStatus = "Disconnected") }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        fused.removeLocationUpdates(callback)
        mqtt?.disconnect()
        super.onDestroy()
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, getString(R.string.location_channel), NotificationManager.IMPORTANCE_LOW))
    }

    companion object {
        const val ACTION_START = "org.lifelane.START"
        const val ACTION_COMPLETE = "org.lifelane.COMPLETE"
        const val ACTION_CANCEL = "org.lifelane.CANCEL"
        const val ACTION_RETRY = "org.lifelane.RETRY"
        const val EXTRA_AMBULANCE_ID = "ambulanceId"
        const val EXTRA_TRIP_ID = "tripId"
        const val EXTRA_PRIORITY = "priority"
        const val EXTRA_CONDITION = "condition"
        const val EXTRA_DESTINATION = "destination"
        const val EXTRA_DEST_LAT = "destLat"
        const val EXTRA_DEST_LON = "destLon"
        const val EXTRA_JUNC_LAT = "juncLat"
        const val EXTRA_JUNC_LON = "juncLon"
        private const val CHANNEL_ID = "lifelane_emergency_location"
        private const val NOTIFICATION_ID = 1001
        private const val JUNCTION_LAT = 9.451500
        private const val JUNCTION_LON = 77.553500

        private fun distanceMetres(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
            val p1 = Math.toRadians(lat1); val p2 = Math.toRadians(lat2)
            val dp = Math.toRadians(lat2 - lat1); val dl = Math.toRadians(lon2 - lon1)
            val a = sin(dp / 2).pow(2) + cos(p1) * cos(p2) * sin(dl / 2).pow(2)
            return 6_371_000.0 * 2 * atan2(sqrt(a), sqrt(1 - a))
        }

        private fun bearing(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
            val p1 = Math.toRadians(lat1); val p2 = Math.toRadians(lat2); val dl = Math.toRadians(lon2 - lon1)
            val x = sin(dl) * cos(p2)
            val y = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl)
            return (Math.toDegrees(atan2(x, y)) + 360) % 360
        }
    }
}
