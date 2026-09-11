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

class TripViewModel(application: Application) : AndroidViewModel(application) {
    private val preferences = application.getSharedPreferences("lifelane_driver", 0)
    private val rememberedAmbulance = preferences.getString("ambulance_id", "").orEmpty()
    private val savedRecentHospitals =
        preferences.getStringSet("recent_hospitals", emptySet()).orEmpty().toList().sorted()

    private val _state = MutableStateFlow(
        TripUiState(
            ambulanceId    = rememberedAmbulance,
            recentHospitals = savedRecentHospitals,
        )
    )
    val state = _state.asStateFlow()

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
                        mqttStatus       = service.mqttStatus,
                        distanceMetres   = service.distanceMetres,
                        detectedApproach = service.detectedApproach,
                        requestStatus    = service.requestStatus,
                        signalStatus     = newSignalStatus,
                        signalArms       = SignalArms.fromString(newSignalStatus),
                    )
                }
            }
        }
    }

    // ── Navigation ────────────────────────────────────────────────────────────────────────────────

    fun finishSplash() { _state.value = _state.value.copy(screen = AppScreen.LOGIN) }

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
        if (_state.value.rememberAmbulance) preferences.edit { putString("ambulance_id", id) }
        else preferences.edit { remove("ambulance_id") }
        _state.value = _state.value.copy(
            ambulanceId      = id,
            screen           = AppScreen.PRIORITY,
            priority         = null, condition = null,
            destination      = "", selectedHospital = null,
            destinationLat   = null, destinationLon = null,
            message          = null,
        )
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
        )
        // Only fetch if we haven't already fetched for these coordinates.
        if (lastFetchedCoords == null) {
            fetchHospitalsByLocation(lat, lon)
        }
    }

    fun updatePreTripLocation(lat: Double, lon: Double, accuracy: Float? = null) {
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
                    nearbyHospitals  = hospitals,
                    hospitalsLoading = false,
                    hospitalCityName = cityName,
                    hospitalsError   = if (isOfflineFallback)
                        "No online data for $cityName — showing offline hospitals. Tap refresh to retry."
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
        val hospitals = (current.recentHospitals + current.destination).distinct().takeLast(5)
        preferences.edit { putStringSet("recent_hospitals", hospitals.toSet()) }

        val hospital = current.selectedHospital
            ?: current.nearbyHospitals.firstOrNull()
            ?: HospitalRepository.RAJAPALAYAM_FALLBACK.first()

        val started = current.copy(
            tripId           = tripId,
            emergencyActive  = true,
            selectedHospital = hospital,
            destinationLat   = hospital.latitude,
            destinationLon   = hospital.longitude,
            startTime        = Instant.now(),
            screen           = AppScreen.EMERGENCY,
            gpsStatus        = "Acquiring GPS",
            mqttStatus       = "Connecting",
            requestStatus    = "Not requested",
            signalStatus     = "Awaiting junction status",
            signalArms       = SignalArms(),
            recentHospitals  = hospitals,
        )
        _state.value = started
        TripStatusRepository.update { started }

        ContextCompat.startForegroundService(
            getApplication(),
            Intent(getApplication(), EmergencyLocationService::class.java).apply {
                action = EmergencyLocationService.ACTION_START
                putExtra(EmergencyLocationService.EXTRA_AMBULANCE_ID,  started.ambulanceId)
                putExtra(EmergencyLocationService.EXTRA_TRIP_ID,       started.tripId)
                putExtra(EmergencyLocationService.EXTRA_PRIORITY,      priority.name)
                putExtra(EmergencyLocationService.EXTRA_CONDITION,     condition.name)
                putExtra(EmergencyLocationService.EXTRA_DESTINATION,   started.destination)
                putExtra(EmergencyLocationService.EXTRA_DEST_LAT,      hospital.latitude)
                putExtra(EmergencyLocationService.EXTRA_DEST_LON,      hospital.longitude)
            }
        )
    }

    fun showLiveGps()         { _state.value = _state.value.copy(screen = AppScreen.LIVE_GPS) }
    fun showEmergency()       { _state.value = _state.value.copy(screen = AppScreen.EMERGENCY) }
    fun requestDelivery()     { _state.value = _state.value.copy(screen = AppScreen.DELIVER_CONFIRM) }
    fun requestCancel()       { _state.value = _state.value.copy(screen = AppScreen.CANCEL_CONFIRM) }
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
            message = "Precise location permission is required before an emergency route can start."
        )
    }

    fun stopTrip(cancelled: Boolean) {
        getApplication<Application>().startService(
            Intent(getApplication(), EmergencyLocationService::class.java).apply {
                action = if (cancelled) EmergencyLocationService.ACTION_CANCEL
                         else           EmergencyLocationService.ACTION_COMPLETE
            }
        )
        _state.value = TripUiState(
            screen            = AppScreen.AMBULANCE,
            driverId          = _state.value.driverId,
            ambulanceId       = _state.value.ambulanceId,
            rememberAmbulance = _state.value.rememberAmbulance,
            recentHospitals   = _state.value.recentHospitals,
            // Preserve fetched hospitals so the next trip doesn't reload immediately
            nearbyHospitals   = _state.value.nearbyHospitals,
            hospitalCityName  = _state.value.hospitalCityName,
            message           = if (cancelled)
                "Emergency cancelled and transmissions stopped."
            else
                "Trip completed and transmissions stopped.",
        )
    }
}
