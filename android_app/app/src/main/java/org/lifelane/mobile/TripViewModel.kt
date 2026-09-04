package org.lifelane.mobile

import android.app.Application
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class TripViewModel(application: Application) : AndroidViewModel(application) {
    private val _state = MutableStateFlow(TripUiState())
    val state = _state.asStateFlow()

    init {
        viewModelScope.launch {
            TripStatusRepository.serviceState.collectLatest { service ->
                if (_state.value.emergencyActive) {
                    _state.value = _state.value.copy(
                        latitude = service.latitude,
                        longitude = service.longitude,
                        accuracyMetres = service.accuracyMetres,
                        speedMps = service.speedMps,
                        headingDegrees = service.headingDegrees,
                        gpsStatus = service.gpsStatus,
                        mqttStatus = service.mqttStatus,
                        distanceMetres = service.distanceMetres,
                        detectedApproach = service.detectedApproach,
                        requestStatus = service.requestStatus,
                        signalStatus = service.signalStatus,
                    )
                }
            }
        }
    }

    fun login(driverId: String) {
        if (driverId.isBlank()) {
            _state.value = _state.value.copy(message = "Enter a driver ID")
        } else {
            _state.value = _state.value.copy(driverId = driverId.trim(), screen = AppScreen.AMBULANCE, message = null)
        }
    }

    fun selectAmbulance(id: String) {
        _state.value = _state.value.copy(ambulanceId = id, screen = AppScreen.PICKUP)
    }

    fun confirmPickup() { _state.value = _state.value.copy(screen = AppScreen.PRIORITY) }
    fun setPriority(value: PatientPriority) { _state.value = _state.value.copy(priority = value, screen = AppScreen.CONDITION) }
    fun setCondition(value: PatientCondition) { _state.value = _state.value.copy(condition = value, screen = AppScreen.DESTINATION) }
    fun setDestination(value: String) {
        if (value.isBlank()) _state.value = _state.value.copy(message = "Enter a destination hospital")
        else _state.value = _state.value.copy(destination = value.trim(), message = null)
    }

    fun startTrip() {
        val current = _state.value
        if (current.destination.isBlank()) return
        val tripId = "TRIP-${UUID.randomUUID().toString().take(8).uppercase()}"
        val started = current.copy(
            tripId = tripId,
            emergencyActive = true,
            startTime = Instant.now(),
            screen = AppScreen.EMERGENCY,
            gpsStatus = "Starting",
            mqttStatus = "Connecting",
        )
        _state.value = started
        TripStatusRepository.update { started }
        val intent = Intent(getApplication(), EmergencyLocationService::class.java).apply {
            action = EmergencyLocationService.ACTION_START
            putExtra(EmergencyLocationService.EXTRA_AMBULANCE_ID, started.ambulanceId)
            putExtra(EmergencyLocationService.EXTRA_TRIP_ID, started.tripId)
            putExtra(EmergencyLocationService.EXTRA_PRIORITY, started.priority.name)
            putExtra(EmergencyLocationService.EXTRA_CONDITION, started.condition.name)
            putExtra(EmergencyLocationService.EXTRA_DESTINATION, started.destination)
        }
        ContextCompat.startForegroundService(getApplication(), intent)
    }

    fun showLiveGps() { _state.value = _state.value.copy(screen = AppScreen.LIVE_GPS) }
    fun showEmergency() { _state.value = _state.value.copy(screen = AppScreen.EMERGENCY) }
    fun requestDelivery() { _state.value = _state.value.copy(screen = AppScreen.DELIVER_CONFIRM) }
    fun requestCancel() { _state.value = _state.value.copy(screen = AppScreen.CANCEL_CONFIRM) }
    fun dismissConfirmation() { _state.value = _state.value.copy(screen = AppScreen.EMERGENCY) }

    fun stopTrip(cancelled: Boolean) {
        val intent = Intent(getApplication(), EmergencyLocationService::class.java).apply {
            action = if (cancelled) EmergencyLocationService.ACTION_CANCEL else EmergencyLocationService.ACTION_COMPLETE
        }
        getApplication<Application>().startService(intent)
        _state.value = TripUiState(
            screen = AppScreen.AMBULANCE,
            driverId = _state.value.driverId,
            ambulanceId = _state.value.ambulanceId,
            message = if (cancelled) "Emergency cancelled" else "Patient delivery recorded",
        )
    }
}
