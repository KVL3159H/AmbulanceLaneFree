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

data class TripUiState(
    val screen: AppScreen = AppScreen.SPLASH,
    val driverId: String = "",
    val ambulanceId: String = "",
    val rememberAmbulance: Boolean = false,
    val recentHospitals: List<String> = emptyList(),
    val tripId: String = "",
    val priority: PatientPriority? = null,
    val condition: PatientCondition? = null,
    val destination: String = "",
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
    val message: String? = null,
)
