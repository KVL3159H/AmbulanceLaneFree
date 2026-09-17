package org.lifelane.mobile

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

object TripStatusRepository {
    private val _serviceState = MutableStateFlow(TripUiState())
    val serviceState = _serviceState.asStateFlow()

    fun update(block: (TripUiState) -> TripUiState) {
        _serviceState.update(block)
    }
}
