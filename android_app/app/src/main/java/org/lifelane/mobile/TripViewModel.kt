package org.lifelane.mobile

import android.app.Application
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class TripViewModel(application: Application) : AndroidViewModel(application) {
    private val preferences = application.getSharedPreferences("lifelane_driver", 0)
    private val rememberedAmbulance = preferences.getString("ambulance_id", "").orEmpty()
    private val savedRecentHospitals =
        preferences.getStringSet("recent_hospitals", emptySet()).orEmpty().toList().sorted()
    private val savedTheme = runCatching {
        ThemeMode.valueOf(preferences.getString("theme_mode", ThemeMode.SYSTEM.name).orEmpty())
    }.getOrDefault(ThemeMode.SYSTEM)
    private val restoredActive = preferences.getBoolean("active_trip", false)
    private val restoredPriority = runCatching {
        PatientPriority.valueOf(preferences.getString("active_priority", "").orEmpty())
    }.getOrNull()
    private val restoredCondition = runCatching {
        PatientCondition.valueOf(preferences.getString("active_condition", "").orEmpty())
    }.getOrNull()
    private val savedTrips = decodeTripHistory(preferences.getString("trip_history", "[]").orEmpty())

    private val _state = MutableStateFlow(
        TripUiState(
            driverId = preferences.getString("active_driver", "").orEmpty(),
            ambulanceId = if (restoredActive) preferences.getString("active_ambulance", rememberedAmbulance).orEmpty() else rememberedAmbulance,
            recentHospitals = savedRecentHospitals,
            themeMode = savedTheme,
            demoHospitalMode = preferences.getBoolean("demo_hospitals", false),
            emergencyActive = restoredActive,
            tripId = preferences.getString("active_trip_id", "").orEmpty(),
            requestId = preferences.getString("active_request_id", "").orEmpty(),
            priority = restoredPriority,
            condition = restoredCondition,
            destination = preferences.getString("active_destination", "").orEmpty(),
            destinationLat = preferences.getString("active_destination_lat", null)?.toDoubleOrNull(),
            destinationLon = preferences.getString("active_destination_lon", null)?.toDoubleOrNull(),
            startTime = preferences.getString("active_started_at", null)?.let { runCatching { Instant.parse(it) }.getOrNull() },
            recentTrips = savedTrips,
        )
    )
    val state = _state.asStateFlow()

    fun brokerHost(): String = preferences.getString("mqtt_host", BuildConfig.MQTT_HOST).orEmpty()
    fun brokerPort(): String = preferences.getInt("mqtt_port", BuildConfig.MQTT_PORT).toString()

    fun saveBroker(host: String, portText: String) {
        val address = host.trim()
        val port = portText.toIntOrNull()
        if (address.isBlank() || address.any { it.isWhitespace() } || address.contains('/') || address.contains(':') || port == null || port !in 1..65535) {
            _state.value = _state.value.copy(message = "Enter the PC's IPv4 address or hostname without a prefix, and a port from 1 to 65535.")
            return
        }
        preferences.edit { putString("mqtt_host", address); putInt("mqtt_port", port) }
        _state.value = _state.value.copy(message = "Connection saved: $address:$port. Start a trip to send GPS to the desktop.")
        if (_state.value.emergencyActive) retryConnections()
    }

    /**
     * Tracks the last (lat, lon) pair for which a hospital fetch was kicked off.
     * Stored as a pair so we re-fetch if the device moves to a different city.
     * Null = never fetched.
     */
    private var lastFetchedCoords: Pair<Double, Double>? = null

    init {
        // Mirror live service state (GPS / MQTT / signal) into UI state during active trips.
        viewModelScope.launch {
            TripStatusRepository.serviceState.collectLatest { service ->
                if (_state.value.emergencyActive) {
                    val newSignalStatus = service.signalStatus
                    _state.value = _state.value.copy(
                        latitude         = service.latitude,
                        longitude        = service.longitude,
                        accuracyMetres   = service.accuracyMetres,
                        speedMps         = service.speedMps,
                        headingDegrees   = service.headingDegrees,
                        gpsStatus        = service.gpsStatus,
                        gpsState         = service.gpsState,
                        locationUpdatedAt = service.locationUpdatedAt,
                        mqttStatus       = service.mqttStatus,
                        mqttState        = service.mqttState,
                        distanceMetres   = service.distanceMetres,
                        nextJunction     = service.nextJunction,
                        clearedJunctionCount = service.clearedJunctionCount,
                        detectedApproach = service.detectedApproach,
                        requestStatus    = service.requestStatus,
                        requestId        = service.requestId.ifBlank { _state.value.requestId },
                        junctionState    = service.junctionState,
                        junctionStage    = service.junctionStage,
                        acknowledgement  = service.acknowledgement,
                        acknowledgementError = service.acknowledgementError,
                        queuePosition    = service.queuePosition,
                        signalStatus     = newSignalStatus,
                        signalArms       = SignalArms.fromString(newSignalStatus),
                    )
                }
            }
        }
    }

    // ── Navigation ────────────────────────────────────────────────────────────────────────────────

    fun finishSplash() { _state.value = _state.value.copy(screen = if (_state.value.emergencyActive) AppScreen.EMERGENCY else AppScreen.LOGIN) }

    fun login(driverId: String, pin: String, remember: Boolean) {
        val message = when {
            driverId.isBlank()       -> "Enter your authorized driver ID."
            pin.length < 4           -> "Enter a PIN of at least four digits."
            pin.any { !it.isDigit() } -> "PIN must contain digits only."
            else                     -> null
        }
        if (message != null) { _state.value = _state.value.copy(message = message); return }
        _state.value = _state.value.copy(
            driverId = driverId.trim(), rememberAmbulance = remember,
            screen = AppScreen.AMBULANCE, message = null,
        )
    }

    fun selectAmbulance(id: String) {
        _state.value = _state.value.copy(
            ambulanceId      = id,
            message          = null,
        )
    }

    fun continueWithAmbulance() {
        val current = _state.value
        if (current.ambulanceId.isBlank()) {
            _state.value = current.copy(message = "Select an authorized ambulance to continue.")
            return
        }
        if (current.rememberAmbulance) preferences.edit { putString("ambulance_id", current.ambulanceId) }
        else preferences.edit { remove("ambulance_id") }
        _state.value = current.copy(screen = AppScreen.HOME, message = null)
    }

    fun startTripSetup() {
        _state.value = _state.value.copy(
            screen = AppScreen.PATIENT, priority = null, condition = null,
            destination = "", selectedHospital = null, message = null,
        )
    }

    fun openHome() { _state.value = _state.value.copy(screen = AppScreen.HOME, message = null) }
    fun openMap() { _state.value = _state.value.copy(screen = AppScreen.MAP, message = null) }
    fun openTrips() { _state.value = _state.value.copy(screen = AppScreen.TRIPS, message = null) }
    fun openSettings() { _state.value = _state.value.copy(screen = AppScreen.SETTINGS, message = null) }

    fun continueFromPatient() {
        val current = _state.value
        _state.value = when {
            current.priority == null -> current.copy(message = "Choose a medical priority.")
            current.condition == null -> current.copy(message = "Choose the reported condition.")
            else -> {
                if (current.latitude != null && current.longitude != null && lastFetchedCoords == null) {
                    fetchHospitalsByLocation(current.latitude, current.longitude)
                }
                current.copy(screen = AppScreen.DESTINATION, message = null)
            }
        }
    }

    fun changeAmbulance() { _state.value = _state.value.copy(screen = AppScreen.AMBULANCE, message = null) }

    fun setThemeMode(mode: ThemeMode) {
        preferences.edit { putString("theme_mode", mode.name) }
        _state.value = _state.value.copy(themeMode = mode)
    }

    fun setDemoHospitalMode(enabled: Boolean) {
        preferences.edit { putBoolean("demo_hospitals", enabled) }
        _state.value = _state.value.copy(demoHospitalMode = enabled)
        if (enabled) loadDemoHospitals()
    }

    fun unlockDeveloperSettings(pin: String): Boolean {
        val valid = pin == "2026"
        _state.value = _state.value.copy(developerUnlocked = valid, message = if (valid) null else "Developer PIN is incorrect.")
        return valid
    }

    fun setPriority(value: PatientPriority) {
        _state.value = _state.value.copy(priority = value, message = null)
    }

    fun continueFromPriority() {
        _state.value = if (_state.value.priority == null)
            _state.value.copy(message = "Select a medical priority before continuing.")
        else _state.value.copy(screen = AppScreen.CONDITION, message = null)
    }

    fun setCondition(value: PatientCondition) {
        _state.value = _state.value.copy(condition = value, message = null)
    }

    fun continueFromCondition() {
        _state.value = if (_state.value.condition == null)
            _state.value.copy(message = "Select the reported patient condition.")
        else {
            val s = _state.value
            // Trigger hospital fetch when we have GPS and haven't fetched yet for these coords.
            if (s.latitude != null && s.longitude != null && lastFetchedCoords == null) {
                fetchHospitalsByLocation(s.latitude, s.longitude)
            }
            s.copy(screen = AppScreen.DESTINATION, message = null)
        }
    }

    // ── Pre-trip location updates ─────────────────────────────────────────────────────────────────

    /**
     * Called every time a GPS fix arrives before the trip starts.
     * Detects city from coordinates and fetches all hospitals there — once per unique location.
     */
    fun onFirstGpsFix(lat: Double, lon: Double, accuracy: Float? = null) {
        _state.value = _state.value.copy(
            latitude       = lat,
            longitude      = lon,
            accuracyMetres = accuracy ?: _state.value.accuracyMetres,
            gpsState = if (accuracy != null && accuracy <= 30f) GpsState.ACCURATE else GpsState.LOW_ACCURACY,
            gpsStatus = if (accuracy != null && accuracy <= 30f) "Accurate" else "Low accuracy",
            locationUpdatedAt = Instant.now(),
        )
        // Only fetch if we haven't already fetched for these coordinates.
        if (lastFetchedCoords == null) {
            fetchHospitalsByLocation(lat, lon)
        }
    }

    fun beginLocationLookup() {
        _state.value = _state.value.copy(
            gpsState = GpsState.LOCATING,
            gpsStatus = "Finding accurate location",
            message = null,
        )
    }

    fun reportLocationUnavailable(detail: String) {
        _state.value = _state.value.copy(
            gpsState = GpsState.UNAVAILABLE,
            gpsStatus = "Location unavailable",
            message = detail,
        )
    }

    fun updatePreTripLocation(
        lat: Double,
        lon: Double,
        accuracy: Float? = null,
        locationTimeMillis: Long = System.currentTimeMillis(),
    ) {
        val ageMillis = (System.currentTimeMillis() - locationTimeMillis).coerceAtLeast(0L)
        if (ageMillis > 30_000L) {
            _state.value = _state.value.copy(
                latitude = lat,
                longitude = lon,
                accuracyMetres = accuracy,
                gpsState = GpsState.LAST_KNOWN,
                gpsStatus = "Last known location",
                locationUpdatedAt = Instant.ofEpochMilli(locationTimeMillis),
                message = "Only a previous location is available. Waiting for a fresh GPS fix.",
            )
            if (lastFetchedCoords == null) fetchHospitalsByLocation(lat, lon)
            return
        }
        onFirstGpsFix(lat, lon, accuracy)
    }

    // ── Hospital fetching ─────────────────────────────────────────────────────────────────────────

    /**
     * Core fetch: reverse-geocodes [lat],[lon] to get the real city name,
     * then fetches ALL hospitals / clinics / doctors / pharmacies in that city via Overpass.
     *
     * Set [force] = true (Refresh button) to bypass the "already fetched" guard.
     */
    fun fetchHospitalsByLocation(lat: Double, lon: Double, force: Boolean = false) {
        if (_state.value.demoHospitalMode) {
            loadDemoHospitals(lat, lon)
            return
        }
        if (!force && lastFetchedCoords != null) return
        lastFetchedCoords = lat to lon

        _state.value = _state.value.copy(
            hospitalsLoading    = true,
            hospitalsError      = null,
            hospitalSearchQuery = "",
        )

        viewModelScope.launch {
            try {
                // fetchByLocation returns (detectedCityName, sortedHospitalList)
                val (cityName, hospitals) = HospitalRepository.fetchByLocation(lat, lon)

                val isOfflineFallback = hospitals.all { it.id.startsWith("RJP-") }

                _state.value = _state.value.copy(
                    nearbyHospitals  = if (isOfflineFallback) emptyList() else hospitals,
                    hospitalsLoading = false,
                    hospitalCityName = cityName,
                    hospitalDataIsDemo = false,
                    hospitalsError   = if (isOfflineFallback)
                        "Live hospital data is unavailable. Enable Demo hospital data in Developer Settings to use samples."
                    else null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    hospitalsLoading = false,
                    hospitalsError   = "Could not load hospitals. Check your internet connection.",
                )
            }
        }
    }

    private fun loadDemoHospitals(lat: Double? = _state.value.latitude, lon: Double? = _state.value.longitude) {
        val originLat = lat ?: 9.4515
        val originLon = lon ?: 77.5535
        _state.value = _state.value.copy(
            nearbyHospitals = HospitalRepository.withDistances(HospitalRepository.RAJAPALAYAM_FALLBACK, originLat, originLon)
                .map { it.copy(isDemo = true) },
            hospitalCityName = "Rajapalayam",
            hospitalsLoading = false,
            hospitalsError = null,
            hospitalDataIsDemo = true,
        )
    }

    /**
     * Refresh button — clears the fetch guard and re-runs the full location-based fetch.
     */
    fun refreshHospitals() {
        val s   = _state.value
        val lat = s.latitude  ?: return
        val lon = s.longitude ?: return
        lastFetchedCoords = null
        fetchHospitalsByLocation(lat, lon, force = true)
    }

    /** Live search/filter text update. */
    fun setHospitalSearchQuery(query: String) {
        _state.value = _state.value.copy(hospitalSearchQuery = query)
    }

    fun reportMapError(error: String?) {
        _state.value = _state.value.copy(mapError = error)
    }

    // ── Hospital selection ────────────────────────────────────────────────────────────────────────

    fun selectHospital(hospital: HospitalDestination) {
        _state.value = _state.value.copy(
            destination      = hospital.name,
            selectedHospital = hospital,
            destinationLat   = hospital.latitude,
            destinationLon   = hospital.longitude,
            message          = null,
        )
    }

    fun setDestination(value: String) {
        val matched = _state.value.nearbyHospitals
            .find { it.name.equals(value.trim(), ignoreCase = true) }
        _state.value = _state.value.copy(
            destination      = value,
            selectedHospital = matched,
            destinationLat   = matched?.latitude,
            destinationLon   = matched?.longitude,
            message          = null,
        )
    }

    fun useRecentHospital(value: String) {
        val matched = _state.value.nearbyHospitals
            .find { it.name.equals(value.trim(), ignoreCase = true) }
        _state.value = _state.value.copy(
            destination      = value,
            selectedHospital = matched,
            destinationLat   = matched?.latitude,
            destinationLon   = matched?.longitude,
            message          = null,
        )
    }

    fun reviewTrip() {
        val dest = _state.value.destination.trim()
        if (dest.isBlank()) {
            _state.value = _state.value.copy(message = "Select or enter a destination hospital.")
            return
        }
        val matched = _state.value.selectedHospital
            ?: _state.value.nearbyHospitals.find { it.name.contains(dest, ignoreCase = true) }
            ?: _state.value.nearbyHospitals.firstOrNull()
            ?: HospitalRepository.RAJAPALAYAM_FALLBACK.first()
        _state.value = _state.value.copy(
            destination      = dest,
            selectedHospital = matched,
            destinationLat   = matched.latitude,
            destinationLon   = matched.longitude,
            screen           = AppScreen.CONFIRM,
            message          = null,
        )
    }

    // ── Trip lifecycle ────────────────────────────────────────────────────────────────────────────

    fun startTrip() {
        val current   = _state.value
        val priority  = current.priority  ?: return
        val condition = current.condition ?: return
        if (current.destination.isBlank() || current.ambulanceId.isBlank()) return

        val tripId    = "TRIP-${UUID.randomUUID().toString().take(8).uppercase()}"
        val requestId = "REQ-${UUID.randomUUID().toString().take(10).uppercase()}"
        val hospitals = (current.recentHospitals + current.destination).distinct().takeLast(5)
        preferences.edit { putStringSet("recent_hospitals", hospitals.toSet()) }

        val hospital = current.selectedHospital
            ?: current.nearbyHospitals.firstOrNull()
            ?: HospitalRepository.RAJAPALAYAM_FALLBACK.first()

        val started = current.copy(
            tripId           = tripId,
            requestId        = requestId,
            emergencyActive  = true,
            selectedHospital = hospital,
            destinationLat   = hospital.latitude,
            destinationLon   = hospital.longitude,
            startTime        = Instant.now(),
            screen           = AppScreen.EMERGENCY,
            gpsStatus        = "Acquiring GPS",
            gpsState         = GpsState.LOCATING,
            mqttStatus       = "Connecting",
            mqttState        = ConnectionState.CONNECTING,
            requestStatus    = "Not requested",
            signalStatus     = "Awaiting junction status",
            signalArms       = SignalArms(),
            junctionStage    = JunctionStage.MONITORING_ROUTE,
            acknowledgement = null,
            recentHospitals  = hospitals,
        )
        _state.value = started
        TripStatusRepository.update { started }
        preferences.edit {
            putBoolean("active_trip", true)
            putString("active_driver", started.driverId)
            putString("active_ambulance", started.ambulanceId)
            putString("active_trip_id", started.tripId)
            putString("active_request_id", started.requestId)
            putString("active_priority", priority.name)
            putString("active_condition", condition.name)
            putString("active_destination", started.destination)
            putString("active_destination_lat", hospital.latitude.toString())
            putString("active_destination_lon", hospital.longitude.toString())
            putString("active_started_at", started.startTime.toString())
        }

        ContextCompat.startForegroundService(
            getApplication(),
            Intent(getApplication(), EmergencyLocationService::class.java).apply {
                action = EmergencyLocationService.ACTION_START
                putExtra(EmergencyLocationService.EXTRA_AMBULANCE_ID,  started.ambulanceId)
                putExtra(EmergencyLocationService.EXTRA_TRIP_ID,       started.tripId)
                putExtra(EmergencyLocationService.EXTRA_REQUEST_ID,    started.requestId)
                putExtra(EmergencyLocationService.EXTRA_PRIORITY,      priority.name)
                putExtra(EmergencyLocationService.EXTRA_CONDITION,     condition.name)
                putExtra(EmergencyLocationService.EXTRA_DESTINATION,   started.destination)
                putExtra(EmergencyLocationService.EXTRA_DEST_ID,       hospital.id)
                putExtra(EmergencyLocationService.EXTRA_DEST_LAT,      hospital.latitude)
                putExtra(EmergencyLocationService.EXTRA_DEST_LON,      hospital.longitude)
            }
        )
    }

    fun showLiveGps()         { _state.value = _state.value.copy(screen = AppScreen.LIVE_GPS) }
    fun showEmergency()       { _state.value = _state.value.copy(screen = AppScreen.EMERGENCY) }
    fun requestDelivery()     { _state.value = _state.value.copy(screen = AppScreen.DELIVER_CONFIRM) }
    fun requestCancel()       { _state.value = _state.value.copy(screen = AppScreen.CANCEL_CONFIRM) }
    fun setCancellationReason(reason: String) { _state.value = _state.value.copy(cancellationReason = reason.take(120)) }
    fun dismissConfirmation() { _state.value = _state.value.copy(screen = AppScreen.EMERGENCY) }
    fun backTo(screen: AppScreen) { _state.value = _state.value.copy(screen = screen, message = null) }

    fun retryConnections() {
        getApplication<Application>().startService(
            Intent(getApplication(), EmergencyLocationService::class.java).apply {
                action = EmergencyLocationService.ACTION_RETRY
            }
        )
    }

    fun reportPermissionDenied() {
        _state.value = _state.value.copy(
            message = "Precise location permission is required before an emergency route can start.",
            gpsState = GpsState.PERMISSION_REQUIRED,
            gpsStatus = "Location permission required",
        )
    }

    fun stopTrip(cancelled: Boolean, cancellationReason: String = _state.value.cancellationReason) {
        val ending = _state.value
        getApplication<Application>().startService(
            Intent(getApplication(), EmergencyLocationService::class.java).apply {
                action = if (cancelled) EmergencyLocationService.ACTION_CANCEL
                         else           EmergencyLocationService.ACTION_COMPLETE
                putExtra(EmergencyLocationService.EXTRA_CANCEL_REASON, cancellationReason)
            }
        )
        val summary = TripSummary(
            tripId = ending.tripId, ambulanceId = ending.ambulanceId,
            urgency = ending.priority ?: PatientPriority.GREEN,
            destination = ending.destination, startedAt = ending.startTime ?: Instant.now(),
            endedAt = Instant.now(), cancelled = cancelled,
            distanceMetres = ending.distanceMetres,
            junctionsRequested = if (ending.junctionStage in setOf(JunctionStage.REQUEST_SENT, JunctionStage.REQUEST_VALIDATED, JunctionStage.WAITING_FOR_PRIORITY, JunctionStage.PRIORITY_GRANTED, JunctionStage.JUNCTION_CLEARED, JunctionStage.NORMAL_CYCLE_RESTORED)) 1 else 0,
            junctionsGranted = if (ending.junctionStage in setOf(JunctionStage.PRIORITY_GRANTED, JunctionStage.JUNCTION_CLEARED, JunctionStage.NORMAL_CYCLE_RESTORED)) 1 else 0,
            junctionsCleared = if (ending.junctionStage in setOf(JunctionStage.JUNCTION_CLEARED, JunctionStage.NORMAL_CYCLE_RESTORED)) 1 else 0,
            gpsInterruptions = ending.gpsInterruptions,
            networkInterruptions = ending.networkInterruptions,
            cancellationReason = cancellationReason.takeIf { cancelled && it.isNotBlank() },
        )
        val history = (listOf(summary) + ending.recentTrips).distinctBy { it.tripId }.take(50)
        preferences.edit {
            remove("active_trip"); remove("active_driver"); remove("active_ambulance"); remove("active_trip_id"); remove("active_request_id")
            remove("active_priority"); remove("active_condition"); remove("active_destination")
            remove("active_destination_lat"); remove("active_destination_lon"); remove("active_started_at")
            putString("trip_history", encodeTripHistory(history))
        }
        _state.value = TripUiState(
            screen            = AppScreen.TRIP_SUMMARY,
            driverId          = _state.value.driverId,
            ambulanceId       = _state.value.ambulanceId,
            rememberAmbulance = _state.value.rememberAmbulance,
            recentHospitals   = _state.value.recentHospitals,
            // Preserve fetched hospitals so the next trip doesn't reload immediately
            nearbyHospitals   = _state.value.nearbyHospitals,
            hospitalCityName  = _state.value.hospitalCityName,
            themeMode         = ending.themeMode,
            demoHospitalMode  = ending.demoHospitalMode,
            hospitalDataIsDemo = ending.hospitalDataIsDemo,
            recentTrips       = history,
            completedTrip     = summary,
            message           = if (cancelled)
                "Emergency cancelled and transmissions stopped."
            else
                "Trip completed and transmissions stopped.",
        )
    }

    private fun decodeTripHistory(raw: String): List<TripSummary> = runCatching {
        val array = JSONArray(raw)
        (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            TripSummary(
                tripId = item.getString("tripId"), ambulanceId = item.getString("ambulanceId"),
                urgency = PatientPriority.valueOf(item.getString("urgency")), destination = item.getString("destination"),
                startedAt = Instant.parse(item.getString("startedAt")), endedAt = Instant.parse(item.getString("endedAt")),
                cancelled = item.getBoolean("cancelled"),
                distanceMetres = if (item.isNull("distanceMetres")) null else item.getDouble("distanceMetres"),
                junctionsRequested = item.optInt("junctionsRequested"), junctionsGranted = item.optInt("junctionsGranted"),
                junctionsCleared = item.optInt("junctionsCleared"), gpsInterruptions = item.optInt("gpsInterruptions"),
                networkInterruptions = item.optInt("networkInterruptions"), cancellationReason = item.optString("cancellationReason").takeIf(String::isNotBlank),
            )
        }
    }.getOrDefault(emptyList())

    private fun encodeTripHistory(history: List<TripSummary>): String = JSONArray().apply {
        history.forEach { trip ->
            put(JSONObject().apply {
                put("tripId", trip.tripId); put("ambulanceId", trip.ambulanceId); put("urgency", trip.urgency.name)
                put("destination", trip.destination); put("startedAt", trip.startedAt.toString()); put("endedAt", trip.endedAt.toString())
                put("cancelled", trip.cancelled); put("distanceMetres", trip.distanceMetres ?: JSONObject.NULL)
                put("junctionsRequested", trip.junctionsRequested); put("junctionsGranted", trip.junctionsGranted)
                put("junctionsCleared", trip.junctionsCleared); put("gpsInterruptions", trip.gpsInterruptions)
                put("networkInterruptions", trip.networkInterruptions); put("cancellationReason", trip.cancellationReason ?: "")
            })
        }
    }.toString()
}
