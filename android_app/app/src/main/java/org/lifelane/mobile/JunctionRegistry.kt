package org.lifelane.mobile

import org.json.JSONObject
import kotlin.math.*

data class SupportedJunction(val config: JSONObject, val approach: String,
    val stop: RouteProjection, val exit: RouteProjection) {
    val id: String get() = config.getJSONObject("junction").getString("id")
}

/** Route-ordered registered inbound paths. This does not itself authorize priority. */
class JunctionRegistry(val configurations: List<JSONObject>) {
    init {
        require(configurations.isNotEmpty())
        require(configurations.map { it.getJSONObject("junction").getString("id") }.distinct().size==configurations.size)
    }

    fun upcoming(route: RoutePlan, latitude: Double, longitude: Double, cleared: Set<String>): List<SupportedJunction> {
        val position=route.project(latitude,longitude)
        return configurations.flatMap { config ->
            val junction=config.getJSONObject("junction")
            if(junction.getString("id") in cleared) emptyList() else {
                val geometry=config.getJSONObject("geometry")
                val paths=geometry.getJSONObject("paths")
                paths.keys().asSequence().mapNotNull { side ->
                    val stopPoint=pointAt(config,side,geometry.getJSONObject("stop_progress").getDouble(side))
                    val exitPoint=pointAt(config,side,geometry.getJSONObject("exit_progress").getDouble(side)+
                        config.getJSONObject("detection").optDouble("exit_radius_metres",80.0))
                    val stop=route.project(stopPoint.latitude,stopPoint.longitude)
                    val exit=route.project(exitPoint.latitude,exitPoint.longitude)
                    val expected=geometry.getJSONObject("inbound_bearings").getDouble(side)
                    val tolerance=config.getJSONObject("detection").optDouble("heading_tolerance_degrees",60.0)
                    if(stop.lateral<=15 && exit.lateral<=15 && exit.progress>stop.progress &&
                        stop.progress>=position.progress && abs((stop.heading-expected+540)%360-180)<=tolerance &&
                        abs((exit.heading-exitHeading(config,side)+540)%360-180)<=tolerance)
                        SupportedJunction(config,side,stop,exit) else null
                }.toList().sortedBy { it.stop.lateral }.take(1)
            }
        }.sortedBy { it.stop.progress }
    }

    companion object {
        fun exitHeading(config: JSONObject,side: String): Double {
            val path=config.getJSONObject("geometry").getJSONObject("paths").getJSONArray(side)
            val a=path.getJSONArray(path.length()-2); val b=path.getJSONArray(path.length()-1)
            return (Math.toDegrees(atan2(b.getDouble(0)-a.getDouble(0),b.getDouble(1)-a.getDouble(1)))+360)%360
        }
        fun pointAt(config: JSONObject, side: String, progress: Double): RoutePoint {
            val points=config.getJSONObject("geometry").getJSONObject("paths").getJSONArray(side)
            var remaining=progress.coerceAtLeast(0.0)
            var x=points.getJSONArray(0).getDouble(0)
            var y=points.getJSONArray(0).getDouble(1)
            for(i in 1 until points.length()) {
                val b=points.getJSONArray(i)
                val dx=b.getDouble(0)-x; val dy=b.getDouble(1)-y
                val length=hypot(dx,dy)
                if(length>0 && remaining<=length) { x+=dx*remaining/length; y+=dy*remaining/length; break }
                remaining-=length; x=b.getDouble(0); y=b.getDouble(1)
            }
            val junction=config.getJSONObject("junction")
            val lat=junction.getDouble("latitude")
            return RoutePoint(lat+y/111320,junction.getDouble("longitude")+x/(111320*cos(Math.toRadians(lat))))
        }
    }
}
