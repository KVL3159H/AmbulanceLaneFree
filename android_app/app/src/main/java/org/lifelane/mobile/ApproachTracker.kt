package org.lifelane.mobile

import android.location.Location
import kotlin.math.*

data class GpsSample(val latitude: Double,val longitude: Double,val accuracy: Double,
    val speed: Double,val heading: Double?,val monotonicNanos: Long)

/** Configured inbound path plus multiple moving samples; no coordinate-quadrant grant. */
class ApproachTracker(private val config: org.json.JSONObject) {
    private val detection=config.getJSONObject("detection")
    private val geometry=config.getJSONObject("geometry")
    data class Fix(val side: String?, val heading: Double, val confidence: Int,
                   val distanceToStop: Double, val confirmed: Boolean)
    private val samples=ArrayDeque<GpsSample>()
    private var confirmedSide: String?=null
    private var candidateSide: String?=null
    private var consecutive=0
    private val paths: Map<String,RoutePlan> by lazy {
        val junction=config.getJSONObject("junction")
        val lat=junction.getDouble("latitude"); val lon=junction.getDouble("longitude")
        val configured=geometry.getJSONObject("paths")
        configured.keys().asSequence().associateWith { side ->
            val points=configured.getJSONArray(side)
            RoutePlan((0 until points.length()).map { index ->
                val p=points.getJSONArray(index)
                RoutePoint(lat+p.getDouble(1)/111320,lon+p.getDouble(0)/(111320*cos(Math.toRadians(lat))))
            },0.0,0.0)
        }
    }

    fun reset() { samples.clear(); confirmedSide=null; candidateSide=null; consecutive=0 }

    @Suppress("UNUSED_PARAMETER")
    fun update(location: Location, latitude: Double, longitude: Double): Fix = update(GpsSample(
        location.latitude,location.longitude,location.accuracy.toDouble(),location.speed.toDouble(),
        if(location.hasBearing()) location.bearing.toDouble() else null,location.elapsedRealtimeNanos))

    fun update(location: GpsSample): Fix {
        val previous=samples.lastOrNull()
        if(!location.accuracy.isFinite() || location.accuracy !in 0.0..detection.optDouble("maximum_accuracy_metres",30.0) ||
            location.speed !in 0.0..detection.optDouble("maximum_speed_mps",70.0) ||
            (previous!=null && location.monotonicNanos<=previous.monotonicNanos))
            return Fix(confirmedSide,location.heading ?: 0.0,0,0.0,false)
        if(previous!=null && (location.monotonicNanos-previous.monotonicNanos)/1e9>detection.optDouble("maximum_packet_age_seconds",5.0)) {
            samples.clear(); consecutive=0
        }
        val moving=location.speed>=detection.optDouble("minimum_heading_speed_mps",2.0)
        val first=samples.firstOrNull()
        val heading=if(moving && first!=null && samples.size>=2) {
            val north=(location.latitude-first.latitude)*111320
            val east=(location.longitude-first.longitude)*111320*cos(Math.toRadians(location.latitude))
            (Math.toDegrees(atan2(east,north))+360)%360
        } else ((location.heading ?: 0.0)+360)%360
        fun headingError(side: String)=abs((heading-geometry.getJSONObject("inbound_bearings").getDouble(side)+540)%360-180)
        val side=confirmedSide ?: paths.keys.minBy { paths.getValue(it).project(location.latitude,location.longitude).lateral + if(moving) headingError(it) else 0.0 }
        val path=paths.getValue(side)
        val projection=path.project(location.latitude,location.longitude)
        val distance=geometry.getJSONObject("stop_progress").getDouble(side)-projection.progress
        val junction=config.getJSONObject("junction")
        val jLat=junction.getDouble("latitude"); val jLon=junction.getDouble("longitude")
        val directDistance=hypot((location.latitude-jLat)*111320,(location.longitude-jLon)*111320*cos(Math.toRadians(jLat)))
        val maxCorridor=detection.optDouble("route_corridor_metres",40.0)
        val routeMatch = projection.lateral <= maxCorridor || directDistance <= detection.optDouble("monitoring_distance_metres", 1500.0)
        if(!routeMatch) {
            consecutive=0
            return Fix(confirmedSide,heading,0,distance,false)
        }
        if(candidateSide!=side) consecutive=0
        candidateSide=side
        val last=samples.lastOrNull()
        val lastDirectDist = if(last!=null) hypot((last.latitude-jLat)*111320,(last.longitude-jLon)*111320*cos(Math.toRadians(jLat))) else directDistance
        val decreasing=last!=null && (projection.progress-path.project(last.latitude,last.longitude).progress>1 || (lastDirectDist - directDistance) > 1.0)
        samples.addLast(location); while(samples.size>8) samples.removeFirst()
        val bearingToJunc = (Math.toDegrees(atan2((jLon-location.longitude)*111320*cos(Math.toRadians(jLat)), (jLat-location.latitude)*111320))+360)%360
        val bearingError = abs((heading - bearingToJunc + 540) % 360 - 180)
        val headingMatch = moving && (headingError(side) <= detection.optDouble("heading_tolerance_degrees", 60.0) || bearingError <= detection.optDouble("heading_tolerance_degrees", 60.0))
        val confidence=25+(if(headingMatch)25 else 0)+(if(decreasing)20 else 0)+
            (if(location.accuracy<=15)15 else 0)+(if(samples.size>=3 && moving)15 else 0)
        consecutive=if(headingMatch && decreasing && (distance>0 || directDistance>0)) consecutive+1 else 0
        val confirmed=consecutive>=detection.optInt("consecutive_approach_samples",3) && confidence>=80
        if(confirmed) confirmedSide=side
        return Fix(confirmedSide,heading,confidence,distance,confirmed)
    }
}
