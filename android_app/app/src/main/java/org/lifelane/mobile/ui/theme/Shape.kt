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

object SwiggyShapes {
    val pill = RoundedCornerShape(50)
    val card = RoundedCornerShape(20.dp)
    val sheet = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)
    val control = RoundedCornerShape(14.dp)
    val action = RoundedCornerShape(16.dp)
    val chip = RoundedCornerShape(10.dp)
}

object ProductShapes {
    val pill = SwiggyShapes.pill
    val card = SwiggyShapes.card
    val control = SwiggyShapes.control
    val action = SwiggyShapes.action
}

object WhatsAppShapes {
    val bubbleIncoming = SwiggyShapes.card
    val bubbleOutgoing = SwiggyShapes.card
    val pillBadge = SwiggyShapes.pill
    val card = SwiggyShapes.card
    val actionButton = SwiggyShapes.action
}
