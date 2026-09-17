package org.lifelane.mobile.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

val LifeLaneShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

object ProductShapes {
    val pill = RoundedCornerShape(50)
    val card = RoundedCornerShape(18.dp)
    val control = RoundedCornerShape(14.dp)
    val action = RoundedCornerShape(16.dp)
}

object WhatsAppShapes {
    val bubbleIncoming = ProductShapes.card
    val bubbleOutgoing = ProductShapes.card
    val pillBadge = ProductShapes.pill
    val card = ProductShapes.card
    val actionButton = ProductShapes.action
}
