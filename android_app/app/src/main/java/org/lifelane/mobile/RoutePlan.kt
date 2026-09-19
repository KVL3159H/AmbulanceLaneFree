package org.lifelane.mobile

import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject
import kotlin.math.*

data class RoutePoint(val latitude: Double, val longitude: Double)
data class RouteProjection(val progress: Double, val lateral: Double, val heading: Double)

/** Measured route geometry from OSRM, retained for the active trip. */
data class RoutePlan(val points: List<RoutePoint>, val distance: Double, val duration: Double) {
    fun project(latitude: Double, longitude: Double): RouteProjection {
        var best = RouteProjection(0.0, Double.POSITIVE_INFINITY, 0.0)
        var progress = 0.0
        for ((a,b) in points.zipWithNext()) {
            val scale = cos(Math.toRadians((a.latitude+b.latitude)/2))*111320
            val dx=(b.longitude-a.longitude)*scale; val dy=(b.latitude-a.latitude)*111320
            val length=hypot(dx,dy)
            if(length<0.001) continue
            val px=(longitude-a.longitude)*scale; val py=(latitude-a.latitude)*111320
            val t=((px*dx+py*dy)/(length*length)).coerceIn(0.0,1.0)
            val lateral=hypot(px-t*dx,py-t*dy)
            if(lateral<best.lateral) best=RouteProjection(progress+t*length,lateral,(Math.toDegrees(atan2(dx,dy))+360)%360)
            progress+=length
        }
        return best
    }

    val geometryLength: Double get() = points.zipWithNext().sumOf { (a,b) ->
        hypot((b.latitude-a.latitude)*111320,(b.longitude-a.longitude)*111320*cos(Math.toRadians((a.latitude+b.latitude)/2)))
    }

    companion object {
        fun fetch(latitude: Double, longitude: Double, destinationLat: Double, destinationLon: Double): RoutePlan {
            val connection = URL("https://router.project-osrm.org/route/v1/driving/$longitude,$latitude;$destinationLon,$destinationLat?overview=full&geometries=geojson").openConnection() as HttpURLConnection
            connection.connectTimeout=8000; connection.readTimeout=8000
            try {
                val json=JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                require(json.optString("code")=="Ok") { "Route unavailable" }
                val route=json.getJSONArray("routes").getJSONObject(0)
                val coordinates=route.getJSONObject("geometry").getJSONArray("coordinates")
                val points=(0 until coordinates.length()).map { i ->
                    val point=coordinates.getJSONArray(i); RoutePoint(point.getDouble(1),point.getDouble(0))
                }
                require(points.size>=2)
                return RoutePlan(points,route.getDouble("distance"),route.getDouble("duration"))
            } finally { connection.disconnect() }
        }
    }
}
