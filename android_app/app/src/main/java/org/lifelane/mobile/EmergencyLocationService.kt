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

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let(::publishLocation)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startEmergency(intent)
            ACTION_COMPLETE -> stopEmergency(cancelled = false)
            ACTION_CANCEL -> stopEmergency(cancelled = true)
        }
        return START_NOT_STICKY
    }

    private fun startEmergency(intent: Intent) {
        ambulanceId = intent.getStringExtra(EXTRA_AMBULANCE_ID) ?: return stopSelf()
        tripId = intent.getStringExtra(EXTRA_TRIP_ID) ?: return stopSelf()
        priority = intent.getStringExtra(EXTRA_PRIORITY) ?: "RED"
        condition = intent.getStringExtra(EXTRA_CONDITION) ?: "OTHER"
        destination = intent.getStringExtra(EXTRA_DESTINATION) ?: ""
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
                TripStatusRepository.update {
                    it.copy(
                        signalStatus = json.optString("signalState", "Unknown"),
                        requestStatus = if (selected == ambulanceId) "Selected" else json.optString("requestStatus", "Waiting"),
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
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED
        ) {
            TripStatusRepository.update { it.copy(gpsStatus = "Location permission denied") }
            stopEmergency(cancelled = true)
            return
        }
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1_500L)
            .setMinUpdateIntervalMillis(1_000L)
            .build()
        fused.requestLocationUpdates(request, callback, mainLooper)
        TripStatusRepository.update { it.copy(gpsStatus = "Acquiring GPS", emergencyActive = true) }
    }

    private fun publishLocation(location: Location) {
        if (!::ambulanceId.isInitialized || !validLocation(location)) return
        val distance = distanceMetres(location.latitude, location.longitude, JUNCTION_LAT, JUNCTION_LON)
        val relativeBearing = bearing(JUNCTION_LAT, JUNCTION_LON, location.latitude, location.longitude)
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
        const val EXTRA_AMBULANCE_ID = "ambulanceId"
        const val EXTRA_TRIP_ID = "tripId"
        const val EXTRA_PRIORITY = "priority"
        const val EXTRA_CONDITION = "condition"
        const val EXTRA_DESTINATION = "destination"
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
