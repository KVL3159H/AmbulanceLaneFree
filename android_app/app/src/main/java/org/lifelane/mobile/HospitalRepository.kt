package org.lifelane.mobile

import android.util.Log
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * Fetches real nearby hospitals from OpenStreetMap Overpass API.
 * Falls back to a curated list of Rajapalayam-area hospitals if no internet.
 */
object HospitalRepository {

    private const val TAG = "HospitalRepository"
    private const val OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    private const val SEARCH_RADIUS_M = 10_000  // 10 km

    // Curated real hospitals in and around Rajapalayam, Tamil Nadu
    val RAJAPALAYAM_FALLBACK = listOf(
        HospitalDestination(
            id = "RJP-01",
            name = "Govt. District HQ Hospital",
            specialty = "Government Emergency & Trauma",
            corridorApproach = "North",
            latitude = 9.4521,
            longitude = 77.5563,
            address = "Hospital Rd, Rajapalayam",
            distanceKm = 0.0,
        ),
        HospitalDestination(
            id = "RJP-02",
            name = "Vaidhehi Hospital",
            specialty = "Multi-Specialty & Surgery",
            corridorApproach = "East",
            latitude = 9.4489,
            longitude = 77.5571,
            address = "Srivilliputtur Rd, Rajapalayam",
            distanceKm = 0.0,
        ),
        HospitalDestination(
            id = "RJP-03",
            name = "Lotus Maternity & Nursing Home",
            specialty = "Maternity, Gynecology & General",
            corridorApproach = "South",
            latitude = 9.4534,
            longitude = 77.5545,
            address = "Sankarankovil Rd, Rajapalayam",
            distanceKm = 0.0,
        ),
        HospitalDestination(
            id = "RJP-04",
            name = "Sri Ramakrishna Hospital",
            specialty = "General Surgery & Critical Care",
            corridorApproach = "West",
            latitude = 9.4498,
            longitude = 77.5580,
            address = "Gandhi Nagar, Rajapalayam",
            distanceKm = 0.0,
        ),
        HospitalDestination(
            id = "RJP-05",
            name = "PHC Krishnankoil",
            specialty = "Primary Health Care",
            corridorApproach = "South",
            latitude = 9.4012,
            longitude = 77.5208,
            address = "Krishnankoil, Virudhunagar Dist.",
            distanceKm = 0.0,
        ),
    )

    /**
     * Fetches hospitals near [lat],[lon] from Overpass API.
     * Returns the fallback list on any network or parse error.
     */
    suspend fun fetchNearby(lat: Double, lon: Double): List<HospitalDestination> =
        withContext(Dispatchers.IO) {
            try {
                val query = """
                    [out:json][timeout:15];
                    (
                      node["amenity"~"^(hospital|clinic)${'$'}"](around:$SEARCH_RADIUS_M,$lat,$lon);
                      way["amenity"~"^(hospital|clinic)${'$'}"](around:$SEARCH_RADIUS_M,$lat,$lon);
                      relation["amenity"~"^(hospital|clinic)${'$'}"](around:$SEARCH_RADIUS_M,$lat,$lon);
                    );
                    out center tags;
                """.trimIndent()

                val url = URL(OVERPASS_URL)
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                conn.doOutput = true
                conn.connectTimeout = 12_000
                conn.readTimeout = 18_000

                val body = "data=${java.net.URLEncoder.encode(query, "UTF-8")}"
                conn.outputStream.use { it.write(body.toByteArray()) }

                if (conn.responseCode != 200) {
                    Log.w(TAG, "Overpass returned HTTP ${conn.responseCode}, using fallback")
                    return@withContext withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
                }

                val json = conn.inputStream.bufferedReader().readText()
                val hospitals = parseOverpassResult(json, lat, lon)

                if (hospitals.isEmpty()) {
                    Log.w(TAG, "No hospitals found via Overpass, using fallback")
                    return@withContext withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
                }

                Log.d(TAG, "Fetched ${hospitals.size} hospitals from Overpass")
                hospitals.sortedBy { it.distanceKm }.take(12)
            } catch (e: Exception) {
                Log.e(TAG, "Overpass fetch failed: ${e.message}, using fallback")
                withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
            }
        }

    private fun parseOverpassResult(
        json: String,
        originLat: Double,
        originLon: Double,
    ): List<HospitalDestination> {
        val result = mutableListOf<HospitalDestination>()
        return try {
            val root = JSONObject(json)
            val elements = root.getJSONArray("elements")
            var idCounter = 1

            for (i in 0 until elements.length()) {
                val elem = elements.getJSONObject(i)
                val tags = elem.optJSONObject("tags") ?: continue

                val name = tags.optString("name", "").trim()
                if (name.isBlank()) continue

                // lat/lon from node directly or from center of way/relation
                val lat = when {
                    elem.has("lat") -> elem.getDouble("lat")
                    elem.has("center") -> elem.getJSONObject("center").getDouble("lat")
                    else -> continue
                }
                val lon = when {
                    elem.has("lon") -> elem.getDouble("lon")
                    elem.has("center") -> elem.getJSONObject("center").getDouble("lon")
                    else -> continue
                }

                val amenity = tags.optString("amenity", "hospital")
                val specialty = when (amenity) {
                    "clinic" -> "Medical Clinic"
                    else -> tags.optString("healthcare:speciality",
                        tags.optString("speciality", "General Hospital"))
                        .replaceFirstChar(Char::uppercase)
                        .ifBlank { "General Hospital" }
                }

                val address = buildString {
                    val street = tags.optString("addr:street", "")
                    val city = tags.optString("addr:city", tags.optString("addr:place", ""))
                    if (street.isNotBlank()) append(street)
                    if (city.isNotBlank()) { if (isNotBlank()) append(", "); append(city) }
                    if (isBlank()) append("${name.take(20)} area")
                }

                val distKm = haversineKm(originLat, originLon, lat, lon)
                val approach = bearingApproach(originLat, originLon, lat, lon)

                result.add(
                    HospitalDestination(
                        id = "OSM-${idCounter++}",
                        name = name,
                        specialty = specialty.take(48),
                        corridorApproach = approach,
                        latitude = lat,
                        longitude = lon,
                        address = address.take(60),
                        distanceKm = distKm,
                    )
                )
            }
            result
        } catch (e: Exception) {
            Log.e(TAG, "Parse error: ${e.message}")
            result
        }
    }

    private fun withDistances(
        list: List<HospitalDestination>,
        lat: Double,
        lon: Double,
    ) = list.map { h ->
        h.copy(
            distanceKm = haversineKm(lat, lon, h.latitude, h.longitude),
            corridorApproach = bearingApproach(lat, lon, h.latitude, h.longitude),
        )
    }.sortedBy { it.distanceKm }

    private fun haversineKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val r = 6_371.0
        val p1 = Math.toRadians(lat1); val p2 = Math.toRadians(lat2)
        val dp = Math.toRadians(lat2 - lat1); val dl = Math.toRadians(lon2 - lon1)
        val a = sin(dp / 2).pow(2) + cos(p1) * cos(p2) * sin(dl / 2).pow(2)
        return r * 2 * atan2(sqrt(a), sqrt(1 - a))
    }

    private fun bearingApproach(fromLat: Double, fromLon: Double, toLat: Double, toLon: Double): String {
        val p1 = Math.toRadians(fromLat); val p2 = Math.toRadians(toLat)
        val dl = Math.toRadians(toLon - fromLon)
        val x = sin(dl) * cos(p2)
        val y = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl)
        val bearing = (Math.toDegrees(atan2(x, y)) + 360) % 360
        return when {
            bearing >= 337.5 || bearing < 22.5 -> "North"
            bearing < 67.5 -> "North-East"
            bearing < 112.5 -> "East"
            bearing < 157.5 -> "South-East"
            bearing < 202.5 -> "South"
            bearing < 247.5 -> "South-West"
            bearing < 292.5 -> "West"
            else -> "North-West"
        }
    }
}
