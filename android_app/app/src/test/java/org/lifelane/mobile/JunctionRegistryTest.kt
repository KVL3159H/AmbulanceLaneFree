package org.lifelane.mobile

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import kotlin.math.cos

class JunctionRegistryTest {
    private fun config(): JSONObject = JSONObject(File("../../shared/junction.json").readText())

    @Test fun routeOrdersTwoJunctionsAndSkipsCleared() {
        val first=config()
        val second=JSONObject(first.toString())
        val junction=first.getJSONObject("junction")
        val lat=junction.getDouble("latitude")
        val lon=junction.getDouble("longitude")
        val scale=111320*cos(Math.toRadians(lat))
        second.getJSONObject("junction").put("id","TEST-SECOND").put("controller_id","PI-TEST-SECOND").put("longitude",lon+1000/scale)
        val route=RoutePlan(listOf(RoutePoint(lat-4.0/111320,lon-1000/scale),RoutePoint(lat-4.0/111320,lon+2500/scale)),3500.0,350.0)
        val registry=JunctionRegistry(listOf(second,first))
        val upcoming=registry.upcoming(route,lat-4.0/111320,lon-500/scale,emptySet())
        assertEquals(listOf(junction.getString("id"),"TEST-SECOND"),upcoming.map { it.id })
        assertTrue(upcoming.all { it.approach=="WEST" })
        assertEquals(480.0,upcoming[0].stop.progress-route.project(lat-4.0/111320,lon-500/scale).progress,0.1)
        assertEquals(listOf("TEST-SECOND"),registry.upcoming(route,lat-4.0/111320,lon-500/scale,setOf(junction.getString("id"))).map { it.id })
    }

    @Test fun parallelRoadOutsideCorridorHasNoSupportedJunction() {
        val config=config(); val j=config.getJSONObject("junction")
        val lat=j.getDouble("latitude"); val lon=j.getDouble("longitude")
        val route=RoutePlan(listOf(RoutePoint(lat+0.01,lon-0.02),RoutePoint(lat+0.01,lon+0.02)),4000.0,400.0)
        assertTrue(JunctionRegistry(listOf(config)).upcoming(route,lat+0.01,lon-0.01,emptySet()).isEmpty())
    }

    @Test fun stopLineUsesConfiguredPathProgress() {
        val config=config()
        val stop=JunctionRegistry.pointAt(config,"NORTH",1180.0)
        assertEquals(config.getJSONObject("junction").getDouble("latitude")+20.0/111320,stop.latitude,1e-8)
        assertTrue(stop.longitude<config.getJSONObject("junction").getDouble("longitude"))
    }

    @Test fun northApproachNeedsRepeatedMovingSamplesAndToleratesNoise() {
        val config=config(); val j=config.getJSONObject("junction")
        val tracker=ApproachTracker(config)
        val lat=j.getDouble("latitude"); val lon=j.getDouble("longitude")
        var fix: ApproachTracker.Fix?=null
        for(i in 0..5) {
            fix=tracker.update(GpsSample(lat+(200-12*i)/111320.0,
                lon+(-4+(if(i%2==0) 2 else -2))/(111320*cos(Math.toRadians(lat))),8.0,12.0,180.0,(i+1)*1000000000L))
            if(i<3) assertFalse(fix.confirmed)
        }
        assertTrue(fix!!.confirmed)
        assertEquals("NORTH",fix.side)
    }

    @Test fun stationaryAndPoorAccuracyNeverConfirm() {
        val config=config(); val j=config.getJSONObject("junction")
        val tracker=ApproachTracker(config)
        for(i in 0..9) assertFalse(tracker.update(GpsSample(j.getDouble("latitude")+0.001,
            j.getDouble("longitude"),5.0,0.0,180.0,(i+1)*1000000000L)).confirmed)
        assertFalse(tracker.update(GpsSample(j.getDouble("latitude")+0.001,
            j.getDouble("longitude"),80.0,12.0,180.0,11000000000L)).confirmed)
    }

    @Test fun routeLengthIncludesAClosedLoop() {
        val route=RoutePlan(listOf(RoutePoint(0.0,0.0),RoutePoint(0.001,0.0),RoutePoint(0.0,0.0)),222.64,30.0)
        assertEquals(222.64,route.geometryLength,0.01)
    }

    @Test fun registeredTurnUsesOutboundHeadingAndExitLine() {
        val config=config()
        val points=org.json.JSONArray("[[-4,1200],[-4,20],[-4,0],[0,-4],[20,-4],[1200,-4]]")
        config.getJSONObject("geometry").getJSONObject("paths").put("NORTH",points)
        config.getJSONObject("geometry").getJSONObject("exit_progress").put("NORTH",1225.656854)
        val j=config.getJSONObject("junction"); val lat=j.getDouble("latitude"); val lon=j.getDouble("longitude")
        val route=RoutePlan((0 until points.length()).map { index ->
            val p=points.getJSONArray(index)
            RoutePoint(lat+p.getDouble(1)/111320,lon+p.getDouble(0)/(111320*cos(Math.toRadians(lat))))
        },2405.656854,240.0)
        val upcoming=JunctionRegistry(listOf(config)).upcoming(route,lat+200.0/111320,lon-4/(111320*cos(Math.toRadians(lat))),emptySet())
        assertEquals("NORTH",upcoming.single().approach)
        assertEquals(90.0,JunctionRegistry.exitHeading(config,"NORTH"),0.01)
        assertTrue(upcoming.single().exit.progress>upcoming.single().stop.progress)
    }
}
