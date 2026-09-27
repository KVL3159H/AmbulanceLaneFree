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
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import android.util.Log
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import org.json.JSONObject
import kotlinx.coroutines.*

class EmergencyLocationService : Service() {
    private val fused by lazy { LocationServices.getFusedLocationProviderClient(this) }
    private var mqtt: MqttGateway? = null
    private val sequence = AtomicLong(100)
    private val telemetryPacketsSent = AtomicInteger(0)

    private fun initialBearing(fromLat: Double, fromLon: Double, toLat: Double, toLon: Double): Double {
        val phi1 = Math.toRadians(fromLat)
        val phi2 = Math.toRadians(toLat)
        val dLambda = Math.toRadians(toLon - fromLon)
        val y = Math.sin(dLambda) * Math.cos(phi2)
        val x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda)
        return (Math.toDegrees(Math.atan2(y, x)) + 360.0) % 360.0
    }

    private fun detectApproachSide(bearingFromJunctionToVehicle: Double): String {
        val b = (bearingFromJunctionToVehicle % 360.0 + 360.0) % 360.0
        return when {
            b >= 315.0 || b < 45.0 -> "NORTH"
            b < 135.0 -> "EAST"
            b < 225.0 -> "SOUTH"
            else -> "WEST"
        }
    }

    private fun compassHeading(degrees: Double): String {
        val deg = (degrees % 360.0 + 360.0) % 360.0
        return when {
            deg >= 337.5 || deg < 22.5 -> "N"
            deg < 67.5 -> "NE"
            deg < 112.5 -> "E"
            deg < 157.5 -> "SE"
            deg < 202.5 -> "S"
            deg < 247.5 -> "SW"
            deg < 292.5 -> "W"
            else -> "NW"
        }
    }
    private lateinit var ambulanceId: String
    private lateinit var tripId: String
    private lateinit var requestId: String
    private lateinit var priority: String
    private lateinit var condition: String
    private lateinit var destination: String
    private lateinit var destinationId: String
    private var destinationLat: Double = 9.456500
    private var destinationLon: Double = 77.553500
    private var junctionLat: Double = JUNCTION_LAT
    private var junctionLon: Double = JUNCTION_LON
    private var junctionInitialized: Boolean = false
    private val junctionCatalog by lazy {
        val array=JSONObject(assets.open("junctions.json").bufferedReader().use { it.readText() }).getJSONArray("junctions")
        JunctionRegistry((0 until array.length()).map { array.getJSONObject(it) })
    }
    private var activeJunctionIndex=0
    private val registry get() = junctionCatalog.configurations[activeJunctionIndex]
    private val clearedJunctions=mutableSetOf<String>()
    private val registeredJunctionId get() = registry.getJSONObject("junction").getString("id")
    private val registeredControllerId get() = registry.getJSONObject("junction").getString("controller_id")
    private var tracker: ApproachTracker?=null
    private val approachTracker get() = tracker ?: ApproachTracker(registry).also { tracker=it }
    private var prioritySent = false
    private val serviceScope = CoroutineScope(SupervisorJob()+Dispatchers.Main)
    private var activeRoute: RoutePlan? = null
    private var routeLoading = false
    private var routeAttemptAt = 0L
    private var offRouteSamples = 0
    private var replanAfter = 0L
    private var lastAcceptedLocation: Location? = null
    private var gpsInterruptions = 0
    private var networkInterruptions = 0

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            val location = result.lastLocation
            if (location == null) TripStatusRepository.update { it.copy(gpsStatus = "Finding accurate location", gpsState = GpsState.LOCATING) }
            else publishLocation(location)
        }

        override fun onLocationAvailability(availability: LocationAvailability) {
            if (!availability.isLocationAvailable) {
                gpsInterruptions++
                TripStatusRepository.update { current -> current.copy(gpsStatus = "Location unavailable", gpsState = GpsState.UNAVAILABLE, gpsInterruptions = gpsInterruptions) }
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startEmergency(intent)
            ACTION_COMPLETE -> stopEmergency(cancelled = false)
            ACTION_CANCEL -> stopEmergency(cancelled = true, reason = intent.getStringExtra(EXTRA_CANCEL_REASON).orEmpty())
            ACTION_RETRY -> retryConnections()
        }
        return START_REDELIVER_INTENT
    }

    private fun startEmergency(intent: Intent) {
        if (::tripId.isInitialized && tripId == intent.getStringExtra(EXTRA_TRIP_ID) && mqtt != null) return
        lastAcceptedLocation=null; activeRoute=null; prioritySent=false
        offRouteSamples=0; replanAfter=0; telemetryPacketsSent.set(0)
        clearedJunctions.clear(); activeJunctionIndex=0; tracker=null
        approachTracker.reset()
        ambulanceId = intent.getStringExtra(EXTRA_AMBULANCE_ID) ?: return stopSelf()
        tripId = intent.getStringExtra(EXTRA_TRIP_ID) ?: return stopSelf()
        requestId = intent.getStringExtra(EXTRA_REQUEST_ID) ?: return stopSelf()
        priority = intent.getStringExtra(EXTRA_PRIORITY) ?: "RED"
        condition = intent.getStringExtra(EXTRA_CONDITION) ?: "OTHER"
        destination = intent.getStringExtra(EXTRA_DESTINATION) ?: ""
        destinationId = intent.getStringExtra(EXTRA_DEST_ID) ?: ""
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
            { state ->
                val typed = when {
                    state.equals("Connected", true) -> ConnectionState.CONNECTED
                    state.contains("reconnecting", true) || state.contains("error", true) -> ConnectionState.INTERRUPTED
                    state.contains("connecting", true) -> ConnectionState.CONNECTING
                    else -> ConnectionState.DISCONNECTED
                }
                if (typed == ConnectionState.INTERRUPTED) networkInterruptions++
                TripStatusRepository.update { it.copy(mqttStatus = state, mqttState = typed, networkInterruptions = networkInterruptions) }
            },
            { _ -> /* Applied signals are accepted only from authenticated acknowledgements. */ },
            { acknowledgement -> serviceScope.launch { handleAcknowledgement(acknowledgement) } },
            endpoint = {
                val prefs = getSharedPreferences("lifelane_driver", 0)
                var host = prefs.getString("mqtt_host", BuildConfig.MQTT_HOST).orEmpty()
                if (host.isBlank() || host.startsWith("10.18.230.")) {
                    host = BuildConfig.MQTT_HOST
                    prefs.edit().putString("mqtt_host", host).apply()
                }
                Pair(host, prefs.getInt("mqtt_port", BuildConfig.MQTT_PORT))
            },
        ).also { it.connect() }
        mqtt?.publish(
            "lifelane/ambulance/$ambulanceId/emergency",
            JSONObject().apply {
                put("schemaVersion", 1); put("sequenceNumber", sequence.incrementAndGet())
                put("ambulanceId", ambulanceId); put("tripId", tripId); put("emergencyActive", true)
                put("requestId", requestId)
                put("timestamp", Instant.now().toString())
            }.toString(),
        )
        requestGpsUpdates()
        serviceScope.launch {
            while(isActive) {
                delay(1500)
                TripStatusRepository.update { current ->
                    val stale=current.locationUpdatedAt?.let { java.time.Duration.between(it,Instant.now()).seconds>5 } ?: true
                    val ackStale=current.acknowledgement?.let { java.time.Duration.between(it.receivedAt,Instant.now()).seconds>5 } ?: true
                    current.copy(gpsState=if(stale) GpsState.UNAVAILABLE else current.gpsState,
                        gpsStatus=if(stale) "Location temporarily unavailable" else current.gpsStatus,
                        requestStatus=if(ackStale && current.junctionStage==JunctionStage.PRIORITY_GRANTED) "Controller confirmation expired" else current.requestStatus,
                        junctionState=if(ackStale && current.junctionState==JunctionState.PRIORITY_GREEN) JunctionState.CONTROLLER_VALIDATED else current.junctionState,
                        junctionStage=if(ackStale && current.junctionStage==JunctionStage.PRIORITY_GRANTED) JunctionStage.WAITING_FOR_PRIORITY else current.junctionStage)
                }
            }
        }
    }

    private fun requestGpsUpdates() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            TripStatusRepository.update { it.copy(gpsStatus = "Location permission required", gpsState = GpsState.PERMISSION_REQUIRED, emergencyActive = true) }
            return
        }
        fused.removeLocationUpdates(callback)
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1_500L)
            .setMinUpdateIntervalMillis(1_000L)
            .build()
        fused.requestLocationUpdates(request, callback, mainLooper)
        TripStatusRepository.update { it.copy(gpsStatus = "Finding accurate location", gpsState = GpsState.LOCATING, emergencyActive = true) }
    }

    private fun publishLocation(location: Location) {
        if (!::ambulanceId.isInitialized) return
        if (!validLocation(location)) {
            gpsInterruptions++
            val status = if (!location.hasAccuracy()) "GPS accuracy unavailable" else "GPS inaccurate (${location.accuracy.toInt()} m)"
            TripStatusRepository.update { it.copy(gpsStatus = status, gpsState = GpsState.LOW_ACCURACY, accuracyMetres = if (location.hasAccuracy()) location.accuracy else it.accuracyMetres, gpsInterruptions = gpsInterruptions) }
            return
        }
        val previous = lastAcceptedLocation
        if (previous != null) {
            val elapsedSeconds = ((location.elapsedRealtimeNanos - previous.elapsedRealtimeNanos) / 1_000_000_000.0).coerceAtLeast(0.1)
            val impliedSpeed = previous.distanceTo(location) / elapsedSeconds
            if (impliedSpeed > 70.0) {
                gpsInterruptions++
                TripStatusRepository.update { it.copy(gpsStatus = "Location jump ignored", gpsState = GpsState.LAST_KNOWN, gpsInterruptions = gpsInterruptions) }
                return
            }
        }
        lastAcceptedLocation = location
        if(replanAfter != 0L && System.currentTimeMillis() >= replanAfter) {
            requestId=java.util.UUID.randomUUID().toString()
            prioritySent=false; replanAfter=0; offRouteSamples=0
            approachTracker.reset(); activeRoute=null
            TripStatusRepository.update { it.copy(requestId=requestId, acknowledgement=null, queuePosition=null,
                junctionState=JunctionState.APPROACH_CONFIRMING,requestStatus="Confirming new route approach") }
        }
        // Only the configured, registered laboratory junction is supported.
        junctionLat = registry.getJSONObject("junction").getDouble("latitude")
        junctionLon = registry.getJSONObject("junction").getDouble("longitude")
        if(activeRoute == null && !routeLoading && System.currentTimeMillis()-routeAttemptAt > 15000) {
            routeLoading=true; routeAttemptAt=System.currentTimeMillis()
            serviceScope.launch {
                activeRoute=withContext(Dispatchers.IO) { runCatching { RoutePlan.fetch(location.latitude,location.longitude,destinationLat,destinationLon) }.getOrNull() }
                routeLoading=false
                TripStatusRepository.update { it.copy(activeRoutePoints=activeRoute?.points.orEmpty(),
                    message=if(activeRoute==null) "Route temporarily unavailable" else null) }
            }
        }
        val route=activeRoute
        val upcoming=route?.let { junctionCatalog.upcoming(it,location.latitude,location.longitude,clearedJunctions) }.orEmpty()
        val next=upcoming.firstOrNull()
        if(!prioritySent && replanAfter==0L && next!=null && next.id!=registeredJunctionId) {
            activeJunctionIndex=junctionCatalog.configurations.indexOf(next.config)
            tracker=null; requestId=java.util.UUID.randomUUID().toString()
            junctionLat=registry.getJSONObject("junction").getDouble("latitude")
            junctionLon=registry.getJSONObject("junction").getDouble("longitude")
            TripStatusRepository.update { it.copy(requestId=requestId,acknowledgement=null,queuePosition=null,
                junctionState=JunctionState.JUNCTION_CANDIDATE,detectedApproach="Confirming ambulance approach") }
        }
        val fix = approachTracker.update(location, junctionLat, junctionLon)
        val position=route?.project(location.latitude,location.longitude)
        val relativeBearingFromJunction = initialBearing(junctionLat, junctionLon, location.latitude, location.longitude)
        val quadrantApproach = detectApproachSide(relativeBearingFromJunction)
        val inboundApproach = fix.side ?: quadrantApproach
        val bearingToJunction = initialBearing(location.latitude, location.longitude, junctionLat, junctionLon)
        val bearingCompass = compassHeading(bearingToJunction)
        val travelCompass = compassHeading(fix.heading)
        val travelHeadingStr = "${fix.heading.toInt()}° $travelCompass"

        val pathSide=fix.side ?: upcoming.firstOrNull { it.id==registeredJunctionId }?.approach ?: inboundApproach
        val geometry=registry.getJSONObject("geometry")
        val stopPoint=pathSide.let { JunctionRegistry.pointAt(registry,it,geometry.getJSONObject("stop_progress").getDouble(it)) }
        val exitPoint=pathSide.let { JunctionRegistry.pointAt(registry,it,geometry.getJSONObject("exit_progress").getDouble(it)+registry.getJSONObject("detection").optDouble("exit_radius_metres",80.0)) }
        val stop=stopPoint.let { route?.project(it.latitude,it.longitude) }
        val exit=exitPoint.let { route?.project(it.latitude,it.longitude) }
        val corridor = registry.getJSONObject("detection").optDouble("route_corridor_metres", 150.0).coerceAtLeast(150.0)
        val directDistance = kotlin.math.hypot(
            (location.latitude - junctionLat) * 111320.0,
            (location.longitude - junctionLon) * 111320.0 * kotlin.math.cos(Math.toRadians(junctionLat))
        )
        val routeSupported = registeredJunctionId !in clearedJunctions &&
            ((position != null && stop != null && exit != null && position.lateral <= corridor && stop.lateral <= 35 &&
              exit.lateral <= corridor && exit.progress > stop.progress &&
              kotlin.math.abs((exit.heading - JunctionRegistry.exitHeading(registry, pathSide) + 540) % 360 - 180) <= 60 &&
              kotlin.math.abs((stop.heading - fix.heading + 540) % 360 - 180) <= 60) || directDistance <= 1500.0)
        val distance = when {
            position != null && stop != null && stop.progress >= position.progress -> stop.progress - position.progress
            fix.distanceToStop > 0 -> fix.distanceToStop
            else -> (directDistance - registry.getJSONObject("geometry").optDouble("junction_half_width_metres", 20.0)).coerceAtLeast(0.0)
        }
        val departedRoute = if (directDistance <= 1500.0) {
            fix.distanceToStop > 0 && kotlin.math.abs((bearingToJunction - fix.heading + 540) % 360 - 180) > 110.0
        } else {
            position != null && (position.lateral > corridor ||
                (location.speed >= 2 && kotlin.math.abs((position.heading - fix.heading + 540) % 360 - 180) > 100))
        }
        offRouteSamples = if (departedRoute && fix.distanceToStop > 0) offRouteSamples + 1 else 0
        if (offRouteSamples >= 3 && replanAfter == 0L) {
            if (prioritySent && BuildConfig.DEVICE_SECRET.isNotBlank()) {
                mqtt?.publish("lifelane/junction/$registeredJunctionId/control", signed(JSONObject().apply {
                    put("requestId", requestId); put("tripId", tripId); put("ambulanceId", ambulanceId)
                    put("messageType", "PRIORITY_CANCEL"); put("timestamp", Instant.now().toString())
                }))
            }
            // Wait out the configured bounded recovery before issuing a fresh identity.
            val timing = registry.getJSONObject("timing")
            replanAfter = System.currentTimeMillis() + ((timing.getDouble("maximum_ambulance_green_seconds") +
                timing.getDouble("yellow_seconds") + timing.getDouble("all_red_seconds") + 5) * 1000).toLong()
            activeRoute = null
            TripStatusRepository.update { it.copy(junctionState = JunctionState.CANCELLED,
                requestStatus = "Approach cancelled; recalculating route", acknowledgement = null) }
        }
        val remaining = if (position != null && position.lateral <= corridor) {
            (route.geometryLength - position.progress).coerceAtLeast(0.0)
        } else if (directDistance <= 1500.0) {
            distance
        } else null
        TripStatusRepository.update { it.copy(remainingRouteDistanceMetres = remaining,
            remainingRouteEtaSeconds = if (remaining != null && route != null && route.geometryLength > 0) {
                route.duration * remaining / route.geometryLength
            } else if (remaining != null && location.speed >= 1.5f) {
                (remaining / location.speed.toDouble())
            } else null) }
        val approach = fix.side ?: inboundApproach
        val packetNumber = telemetryPacketsSent.incrementAndGet()
        val json = JSONObject().apply {
            put("schemaVersion", 1)
            put("sequenceNumber", sequence.incrementAndGet())
            put("ambulanceId", ambulanceId)
            put("tripId", tripId)
            put("requestId", requestId)
            put("latitude", location.latitude)
            put("longitude", location.longitude)
            put("accuracyMetres", location.accuracy.toDouble())
            put("speedMps", location.speed.coerceAtLeast(0f).toDouble())
            put("headingDegrees", fix.heading)
            put("travelHeading", fix.heading)
            put("approachSide", inboundApproach)
            put("direction", inboundApproach)
            put("approach", inboundApproach)
            put("inboundApproach", inboundApproach)
            put("compassDirection", travelCompass)
            put("bearingToJunction", bearingToJunction)
            put("bearingCompass", bearingCompass)
            put("distanceToStopLine", distance)
            put("sourceMode", "LIVE_PHONE")
            put("patientPriority", priority)
            put("patientCondition", condition)
            put("destinationHospital", destination)
            put("destinationHospitalId", destinationId)
            put("destinationLatitude", destinationLat)
            put("destinationLongitude", destinationLon)
            put("routeDistanceMetres", remaining ?: JSONObject.NULL)
            put("routeEtaSeconds", TripStatusRepository.serviceState.value.remainingRouteEtaSeconds ?: JSONObject.NULL)
            put("upcomingJunctionId", registeredJunctionId)
            put("supportedJunctionCount", upcoming.size)
            put("emergencyActive", true)
            put("timestamp", Instant.ofEpochMilli(location.time).toString())
        }
        val rawJson = json.toString()
        Log.d("LifeLaneTelemetry", "TX #$packetNumber: approach=$inboundApproach, heading=$travelHeadingStr, bearingToJunction=${bearingToJunction.toInt()}° $bearingCompass, payload=$rawJson")
        mqtt?.publish("lifelane/ambulance/$ambulanceId/telemetry", rawJson)
        if (BuildConfig.DEVICE_SECRET.isNotBlank()) {
            mqtt?.publish("lifelane/ambulance/$ambulanceId/telemetry2", signed(json))
            if (replanAfter == 0L && fix.confirmed && routeSupported && !prioritySent && distance > 0 && (distance <= 300 || (location.speed > 0 && distance / location.speed <= 45)) &&
                TripStatusRepository.serviceState.value.mqttState == ConnectionState.CONNECTED) {
                val request = JSONObject().apply {
                    put("schemaVersion", 2); put("messageType", "PRIORITY_REQUEST")
                    put("requestId", requestId); put("tripId", tripId); put("ambulanceId", ambulanceId)
                    put("junctionId", registeredJunctionId); put("controllerId", registeredControllerId)
                    put("timestamp", Instant.ofEpochMilli(location.time).toString())
                    put("medicalPriority", when(priority) { "RED" -> "Critical"; "YELLOW" -> "Serious"; else -> "Stable" })
                    put("latitude", location.latitude); put("longitude", location.longitude)
                    put("gpsAccuracy", location.accuracy.toDouble()); put("speed", location.speed.toDouble())
                    put("heading", fix.heading)
                    put("approachSide", inboundApproach)
                    put("direction", inboundApproach)
                    put("approach", inboundApproach)
                    put("approachConfidence", fix.confidence)
                    put("travelHeading", fix.heading)
                    put("distanceToStopLine", distance); put("junctionEtaSeconds", if (location.speed > 0.5f) distance / location.speed else 45.0)
                    put("destinationHospitalId", destinationId); put("destinationHospitalName", destination)
                    put("destinationLatitude", destinationLat); put("destinationLongitude", destinationLon)
                    val routeState = TripStatusRepository.serviceState.value
                    val routeDist = routeState.remainingRouteDistanceMetres ?: distance
                    val routeEta = routeState.remainingRouteEtaSeconds ?: (if (location.speed > 0.5f) distance / location.speed else 45.0)
                    put("routeDistanceMetres", routeDist)
                    put("routeEtaSeconds", routeEta)
                    put("supportedJunctionCount", upcoming.size.coerceAtLeast(1))
                }
                Log.d("LifeLanePriority", "Sending Priority Request for $registeredJunctionId from $inboundApproach: $request")
                mqtt?.publish("lifelane/junction/$registeredJunctionId/priority", signed(request))
                prioritySent = true
            }
        }
        TripStatusRepository.update {
            it.copy(
                latitude = location.latitude, longitude = location.longitude,
                accuracyMetres = location.accuracy, speedMps = location.speed.coerceAtLeast(0f),
                headingDegrees = if (location.hasBearing()) location.bearing else fix.heading.toFloat(),
                gpsStatus = if (location.accuracy <= 30f) "Accurate" else "Low accuracy",
                gpsState = if (location.accuracy <= 30f) GpsState.ACCURATE else GpsState.LOW_ACCURACY,
                locationUpdatedAt = Instant.ofEpochMilli(location.time),
                distanceMetres = if (routeSupported && distance <= 1500.0) distance else null,
                detectedApproach = inboundApproach,
                approachDirection = inboundApproach,
                travelHeadingDirection = travelHeadingStr,
                packetsSentCount = packetNumber,
                lastSentPayload = rawJson,
                requestId = requestId,
                nextJunction = if (prioritySent) registry.getJSONObject("junction").getString("name")
                    else next?.config?.getJSONObject("junction")?.getString("name")
                    ?: (if (distance <= 1500.0) registry.getJSONObject("junction").getString("name") else "No supported junction ahead"),
                clearedJunctionCount = clearedJunctions.size,
                junctionState = if(replanAfter!=0L) JunctionState.CANCELLED else if(it.acknowledgement!=null) it.junctionState else if(prioritySent) JunctionState.PRIORITY_REQUESTED else if(!routeSupported) JunctionState.OUTSIDE_COVERAGE else if(fix.confirmed) JunctionState.APPROACH_CONFIRMED else JunctionState.APPROACH_CONFIRMING,
                requestStatus = if(replanAfter!=0L) "Approach cancelled; recalculating route" else if (it.acknowledgement != null) it.requestStatus else if (prioritySent) "Request sent" else if (!fix.confirmed) "Confirming approach ($inboundApproach)" else "Monitoring route",
                junctionStage = if (it.acknowledgement != null) it.junctionStage else if (prioritySent) JunctionStage.REQUEST_SENT else JunctionStage.MONITORING_ROUTE,
            )
        }
    }

    private fun handleAcknowledgement(envelope: JSONObject) {
        val raw=envelope.optString("payload")
        if(BuildConfig.DEVICE_SECRET.isBlank() || raw.isBlank()) return
        // Verify the exact received bytes, independent of JSON key ordering.
        val mac=javax.crypto.Mac.getInstance("HmacSHA256")
        mac.init(javax.crypto.spec.SecretKeySpec(BuildConfig.DEVICE_SECRET.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        val signature=mac.doFinal(raw.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        if(!java.security.MessageDigest.isEqual(signature.toByteArray(),envelope.optString("signature").toByteArray())) return
        val json=runCatching { JSONObject(raw) }.getOrNull() ?: return
        val now = Instant.now()
        val timestamp = runCatching { Instant.parse(json.optString("acknowledgementTimestamp")) }.getOrNull()
        val receivedRequestId = json.optString("requestId")
        val receivedTripId = json.optString("tripId")
        val receivedAmbulanceId = json.optString("ambulanceId")
        val junctionId = json.optString("junctionId")
        val direction = json.optString("grantedApproach").uppercase()
        val status = json.optString("status").uppercase()
        val controllerState = json.optString("controllerState").uppercase()
        val currentApproach = TripStatusRepository.serviceState.value.detectedApproach.uppercase()
        val error = when {
            json.optInt("schemaVersion", -1) != 2 -> "Unsupported acknowledgement schema"
            json.optString("messageType") != "PRIORITY_ACK" -> "Unsupported acknowledgement type"
            receivedRequestId != requestId -> "Acknowledgement request ID does not match"
            receivedTripId != tripId -> "Acknowledgement trip ID does not match"
            receivedAmbulanceId != ambulanceId -> "Acknowledgement ambulance ID does not match"
            junctionId != registeredJunctionId -> "Acknowledgement junction does not match"
            json.optString("controllerId") != registeredControllerId -> "Acknowledgement controller does not match"
            json.optString("mode") != "HARDWARE" -> "Simulation acknowledgement; hardware priority unconfirmed"
            timestamp == null || java.time.Duration.between(timestamp, now).toMillis() !in 0L..5000L -> "Acknowledgement is stale"
            controllerState == "PRIORITY_GREEN" && direction != currentApproach -> "Acknowledgement approach does not match"
            else -> null
        }
        if (error != null) {
            TripStatusRepository.update { it.copy(acknowledgementError = error) }
            return
        }
        val accepted = json.optBoolean("accepted", false)
        val lamps = json.optJSONObject("lampState")
        val appliedGreen = lamps?.length() == 4 && listOf("NORTH", "EAST", "SOUTH", "WEST").all { side ->
            lamps?.optString(side) == if (side == direction) "GREEN" else "RED"
        }
        val grant = accepted && controllerState == "PRIORITY_GREEN" && appliedGreen
        val stage = when {
            !accepted || status == "REJECTED" || controllerState == "FAIL_SAFE" -> JunctionStage.FAILED
            controllerState == "COMPLETED" -> JunctionStage.NORMAL_CYCLE_RESTORED
            grant -> JunctionStage.PRIORITY_GRANTED
            status == "SELECTED" -> JunctionStage.WAITING_FOR_PRIORITY
            else -> JunctionStage.REQUEST_VALIDATED
        }
        val acknowledgement = JunctionAcknowledgement(
            requestId, tripId, ambulanceId, junctionId, accepted, status, direction,
            controllerState, json.optString("rejectionReason"), timestamp!!,
        )
        TripStatusRepository.update {
            it.copy(
                acknowledgement = acknowledgement, acknowledgementError = null,
                junctionState = if(!accepted) JunctionState.REQUEST_REJECTED else if(json.optString("junctionState")=="PRIORITY_GREEN" && !grant) JunctionState.SAFE_TRANSITION else
                    runCatching { JunctionState.valueOf(json.optString("junctionState")) }.getOrDefault(JunctionState.CONTROLLER_VALIDATED),
                queuePosition = json.optInt("queuePosition").takeIf { it > 0 },
                signalStatus = if(lamps!=null) listOf("NORTH","EAST","SOUTH","WEST").joinToString(",") { side -> "$side:${lamps.optString(side,"UNKNOWN")}" } else "Awaiting confirmed lamp state",
                requestStatus = when (stage) {
                    JunctionStage.PRIORITY_GRANTED -> "Priority granted"
                    JunctionStage.JUNCTION_CLEARED -> "Junction cleared"
                    JunctionStage.FAILED -> "Request rejected"
                    JunctionStage.WAITING_FOR_PRIORITY -> "Waiting for safe clearance"
                    JunctionStage.NORMAL_CYCLE_RESTORED -> "Normal signal restored"
                    else -> "Request validated"
                },
                junctionStage = stage,
            )
        }
        if(accepted && controllerState=="COMPLETED" && json.optString("junctionState")=="COMPLETED") {
            clearedJunctions.add(registeredJunctionId)
            prioritySent=false; tracker=null
            requestId=java.util.UUID.randomUUID().toString()
            TripStatusRepository.update { it.copy(clearedJunctionCount=clearedJunctions.size,
                requestId=requestId,acknowledgement=null,queuePosition=null,requestStatus="Normal signal restored; monitoring next junction") }
        }
    }

    private fun validLocation(location: Location): Boolean =
        location.latitude in -90.0..90.0 && location.longitude in -180.0..180.0 &&
            location.hasAccuracy() && location.accuracy in 0f..30f &&
            location.speed.isFinite() && location.speed in 0f..70f &&
            (android.os.SystemClock.elapsedRealtimeNanos() - location.elapsedRealtimeNanos) in 0L..5_000_000_000L &&
            (lastAcceptedLocation == null || location.elapsedRealtimeNanos > lastAcceptedLocation!!.elapsedRealtimeNanos)

    private fun signed(payload: JSONObject): String {
        val raw = payload.toString()
        val mac = javax.crypto.Mac.getInstance("HmacSHA256")
        mac.init(javax.crypto.spec.SecretKeySpec(BuildConfig.DEVICE_SECRET.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        val signature = mac.doFinal(raw.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        return JSONObject().put("payload", raw).put("signature", signature).toString()
    }

    private fun retryConnections() {
        if (!::ambulanceId.isInitialized) return
        TripStatusRepository.update { it.copy(mqttStatus = "Connecting", mqttState = ConnectionState.CONNECTING, gpsStatus = "Finding accurate location", gpsState = GpsState.LOCATING) }
        mqtt?.reconnect()
        requestGpsUpdates()
    }

    private fun stopEmergency(cancelled: Boolean, reason: String = "") {
        fused.removeLocationUpdates(callback)
        if (::ambulanceId.isInitialized && BuildConfig.DEVICE_SECRET.isNotBlank()) {
            mqtt?.publish("lifelane/junction/$registeredJunctionId/control",signed(JSONObject().apply {
                put("requestId",requestId); put("tripId",tripId); put("ambulanceId",ambulanceId)
                put("messageType","PRIORITY_CANCEL"); put("timestamp",Instant.now().toString())
            }))
        }
        if (::ambulanceId.isInitialized) {
            val topic = if (cancelled) "lifelane/ambulance/$ambulanceId/cancel" else "lifelane/ambulance/$ambulanceId/emergency"
            mqtt?.publish(topic, JSONObject().apply {
                put("schemaVersion", 1); put("sequenceNumber", sequence.incrementAndGet())
                put("ambulanceId", ambulanceId); put("tripId", tripId)
                put("requestId", requestId)
                if (cancelled) put("reason", reason.take(120))
                put("emergencyActive", false); put("timestamp", Instant.now().toString())
            }.toString())
        }
        mqtt?.disconnect()
        TripStatusRepository.update { it.copy(emergencyActive = false, gpsStatus = "Stopped", gpsState = GpsState.STOPPED, mqttStatus = "Disconnected", mqttState = ConnectionState.DISCONNECTED) }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        fused.removeLocationUpdates(callback)
        mqtt?.disconnect()
        serviceScope.cancel()
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
        const val EXTRA_REQUEST_ID = "requestId"
        const val EXTRA_PRIORITY = "priority"
        const val EXTRA_CONDITION = "condition"
        const val EXTRA_DESTINATION = "destination"
        const val EXTRA_DEST_ID = "destinationId"
        const val EXTRA_DEST_LAT = "destLat"
        const val EXTRA_DEST_LON = "destLon"
        const val EXTRA_JUNC_LAT = "juncLat"
        const val EXTRA_JUNC_LON = "juncLon"
        const val EXTRA_CANCEL_REASON = "cancelReason"
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
