package org.lifelane.mobile

import java.time.Instant

enum class PatientPriority { RED, YELLOW, GREEN }

enum class PatientCondition(val label: String) {
    CARDIAC("Cardiac emergency"), BREATHING("Breathing difficulty"),
    UNCONSCIOUS("Unconscious"), SEVERE_BLEEDING("Severe bleeding"),
    TRAUMA("Accident or trauma"), PREGNANCY("Pregnancy emergency"),
    STROKE("Stroke symptoms"), BURNS("Burns"), OTHER("Other")
}

enum class AppScreen {
    SPLASH, LOGIN, AMBULANCE, HOME, MAP, TRIPS, SETTINGS, PATIENT,
    PRIORITY, CONDITION, DESTINATION, CONFIRM, EMERGENCY, LIVE_GPS,
    DELIVER_CONFIRM, CANCEL_CONFIRM, TRIP_SUMMARY
}

enum class ThemeMode { SYSTEM, LIGHT, DARK }
enum class JunctionStage {
    MONITORING_ROUTE, JUNCTION_DETECTED, REQUEST_SENT, REQUEST_VALIDATED,
    WAITING_FOR_PRIORITY, PRIORITY_GRANTED, JUNCTION_CLEARED, NORMAL_CYCLE_RESTORED, FAILED
}

data class JunctionAcknowledgement(
    val requestId: String,
    val tripId: String,
    val ambulanceId: String,
    val junctionId: String,
    val accepted: Boolean,
    val status: String,
    val grantedDirection: String,
    val controllerState: String,
    val reason: String,
    val receivedAt: Instant,
)

data class TripSummary(
    val tripId: String,
    val ambulanceId: String,
    val urgency: PatientPriority,
    val destination: String,
    val startedAt: Instant,
    val endedAt: Instant,
    val cancelled: Boolean,
    val distanceMetres: Double?,
    val junctionsRequested: Int,
    val junctionsGranted: Int,
    val junctionsCleared: Int,
    val gpsInterruptions: Int,
    val networkInterruptions: Int,
    val cancellationReason: String? = null,
)

data class HospitalDestination(
    val id: String,
    val name: String,
    val specialty: String,
    val cityName: String = "",                      // city this hospital belongs to (set from reverse geocode)
    val corridorApproach: String,               // "North", "South", "East", "West", "North-East"
    val latitude: Double,
    val longitude: Double,
    val address: String,
    val distanceKm: Double,
    val isDemo: Boolean = false,
    val supportedJunctions: Int = 1,
)

/** Per-arm signal state for the 4-way junction. */
data class SignalArms(
    val north: String = "RED",
    val south: String = "RED",
    val east: String = "RED",
    val west: String = "RED",
) {
    companion object {
        /** Parse a signalStatus string like "NORTH:GREEN,SOUTH:RED,EAST:RED,WEST:RED" */
        fun fromString(raw: String): SignalArms {
            if (!raw.contains(":")) return SignalArms()
            val map = raw.split(",").associate { part ->
                val kv = part.trim().split(":")
                (kv.getOrNull(0)?.uppercase() ?: "") to (kv.getOrNull(1)?.uppercase() ?: "RED")
            }
            return SignalArms(
                north = map["NORTH"] ?: "RED",
                south = map["SOUTH"] ?: "RED",
                east = map["EAST"] ?: "RED",
                west = map["WEST"] ?: "RED",
            )
        }
    }
}

data class TripUiState(
    val screen: AppScreen = AppScreen.SPLASH,
    val driverId: String = "",
    val ambulanceId: String = "",
    val rememberAmbulance: Boolean = false,
    val recentHospitals: List<String> = emptyList(),
    // City hospitals (all hospitals inside the detected/selected city via Overpass, or fallback)
    val nearbyHospitals: List<HospitalDestination> = emptyList(),
    val hospitalsLoading: Boolean = false,
    val hospitalsError: String? = null,
    val hospitalCityName: String = "Finding your location…",
    val hospitalSearchQuery: String = "",            // live text filter on the hospital list
    val tripId: String = "",
    val requestId: String = "",
    val priority: PatientPriority? = null,
    val condition: PatientCondition? = null,
    val destination: String = "",
    val selectedHospital: HospitalDestination? = null,
    val destinationLat: Double? = null,
    val destinationLon: Double? = null,
    val emergencyActive: Boolean = false,
    val startTime: Instant? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val accuracyMetres: Float? = null,
    val speedMps: Float = 0f,
    val headingDegrees: Float = 0f,
    val gpsStatus: String = "Waiting",
    val gpsState: GpsState = GpsState.LOCATING,
    val locationUpdatedAt: Instant? = null,
    val mqttStatus: String = "Disconnected",
    val mqttState: ConnectionState = ConnectionState.DISCONNECTED,
    val nextJunction: String = "LifeLane Demo Junction",
    val clearedJunctionCount: Int = 0,
    val activeRoutePoints: List<RoutePoint> = emptyList(),
    val remainingRouteDistanceMetres: Double? = null,
    val remainingRouteEtaSeconds: Double? = null,
    val distanceMetres: Double? = null,
    val detectedApproach: String = "Not detected",
    val requestStatus: String = "Not requested",
    val junctionState: JunctionState = JunctionState.OUTSIDE_COVERAGE,
    val junctionStage: JunctionStage = JunctionStage.MONITORING_ROUTE,
    val acknowledgement: JunctionAcknowledgement? = null,
    val acknowledgementError: String? = null,
    val queuePosition: Int? = null,
    val signalStatus: String = "Awaiting junction status",
    val signalArms: SignalArms = SignalArms(),
    val message: String? = null,
    val mapZoom: Float = 1.0f,
    val followVehicle: Boolean = true,
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val demoHospitalMode: Boolean = false,
    val hospitalDataIsDemo: Boolean = false,
    val mapError: String? = null,
    val developerUnlocked: Boolean = false,
    val recentTrips: List<TripSummary> = emptyList(),
    val completedTrip: TripSummary? = null,
    val gpsInterruptions: Int = 0,
    val networkInterruptions: Int = 0,
    val cancellationReason: String = "",
)

// Keep a static DEFAULT_HOSPITALS for backward-compat with any references outside the ViewModel
val DEFAULT_HOSPITALS get() = HospitalRepository.RAJAPALAYAM_FALLBACK

