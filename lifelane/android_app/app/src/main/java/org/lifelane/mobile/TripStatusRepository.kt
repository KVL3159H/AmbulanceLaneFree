package org.lifelane.mobile

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

object TripStatusRepository {
    private val _serviceState = MutableStateFlow(TripUiState())
    val serviceState = _serviceState.asStateFlow()

    fun update(block: (TripUiState) -> TripUiState) {
        _serviceState.value = block(_serviceState.value)
    }
}
