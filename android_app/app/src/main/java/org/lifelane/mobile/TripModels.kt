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
    SPLASH, LOGIN, AMBULANCE, PRIORITY, CONDITION, DESTINATION, CONFIRM,
    EMERGENCY, LIVE_GPS, DELIVER_CONFIRM, CANCEL_CONFIRM
}

data class HospitalDestination(
    val id: String,
    val name: String,
    val specialty: String,
    val corridorApproach: String, // "North", "South", "East", "West", "North-East"
    val latitude: Double,
    val longitude: Double,
    val address: String,
    val distanceKm: Double,
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
    // Nearby hospitals (GPS-based from Overpass API, or fallback)
    val nearbyHospitals: List<HospitalDestination> = HospitalRepository.RAJAPALAYAM_FALLBACK,
    val hospitalsLoading: Boolean = false,
    val hospitalsError: String? = null,
    val tripId: String = "",
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
    val mqttStatus: String = "Disconnected",
    val nextJunction: String = "LifeLane Demo Junction",
    val distanceMetres: Double? = null,
    val detectedApproach: String = "Not detected",
    val requestStatus: String = "Not requested",
    val signalStatus: String = "Awaiting junction status",
    val signalArms: SignalArms = SignalArms(),
    val message: String? = null,
    val mapZoom: Float = 1.0f,
    val followVehicle: Boolean = true,
)

// Keep a static DEFAULT_HOSPITALS for backward-compat with any references outside the ViewModel
val DEFAULT_HOSPITALS get() = HospitalRepository.RAJAPALAYAM_FALLBACK

