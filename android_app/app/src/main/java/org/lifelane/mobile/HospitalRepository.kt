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
 * Fetches ALL hospitals/clinics in the city that the device's GPS coordinates fall inside.
 *
 * Flow:
 *  1. reverseGeocode(lat, lon)  →  Nominatim  →  city / town / village name
 *  2. resolveAreaId(cityName)   →  Nominatim search  →  OSM area ID
 *  3. fetchHospitalsInArea(areaId) →  Overpass  →  all amenity=hospital|clinic|doctors|pharmacy
 *  4. Sort results by Haversine distance from the ambulance's current GPS position.
 *  5. Falls back to the 20-hospital curated Rajapalayam list on any network/parse error.
 */
object HospitalRepository {

    private const val TAG = "HospitalRepository"
    private const val OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
    private const val NOMINATIM_URL = "https://nominatim.openstreetmap.org"

    // ── Curated fallback – 20 real Rajapalayam-area hospitals ────────────────────────────────────
    val RAJAPALAYAM_FALLBACK: List<HospitalDestination> = listOf(
        HospitalDestination("RJP-01", "Govt. District HQ Hospital",
            "Government Emergency & Trauma", "Rajapalayam",
            "North", 9.4521, 77.5563, "Hospital Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-02", "Vaidhehi Hospital",
            "Multi-Specialty & Surgery", "Rajapalayam",
            "East", 9.4489, 77.5571, "Srivilliputtur Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-03", "Lotus Maternity & Nursing Home",
            "Maternity, Gynecology & General", "Rajapalayam",
            "South", 9.4534, 77.5545, "Sankarankovil Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-04", "Sri Ramakrishna Hospital",
            "General Surgery & Critical Care", "Rajapalayam",
            "West", 9.4498, 77.5580, "Gandhi Nagar, Rajapalayam", 0.0),
        HospitalDestination("RJP-05", "PHC Krishnankoil",
            "Primary Health Care", "Rajapalayam",
            "South", 9.4012, 77.5208, "Krishnankoil, Virudhunagar Dist.", 0.0),
        HospitalDestination("RJP-06", "Meenakshi Hospital",
            "General Medicine & Paediatrics", "Rajapalayam",
            "East", 9.4510, 77.5590, "Anna Salai, Rajapalayam", 0.0),
        HospitalDestination("RJP-07", "Sree Gokulam Medical College",
            "Teaching Hospital & Trauma", "Rajapalayam",
            "North", 9.4605, 77.5480, "Venkovilpatti, Rajapalayam", 0.0),
        HospitalDestination("RJP-08", "Sundaram Hospital",
            "Orthopaedics & General Surgery", "Rajapalayam",
            "West", 9.4481, 77.5521, "West Car St, Rajapalayam", 0.0),
        HospitalDestination("RJP-09", "Anantham Nursing Home",
            "Obstetrics & Neonatal Care", "Rajapalayam",
            "North", 9.4543, 77.5532, "Subramania Swamy Koil St, Rajapalayam", 0.0),
        HospitalDestination("RJP-10", "Arumugam Hospital",
            "Urology & Laparoscopic Surgery", "Rajapalayam",
            "East", 9.4468, 77.5601, "East Car St, Rajapalayam", 0.0),
        HospitalDestination("RJP-11", "Jeyam Hospital",
            "ENT & General Medicine", "Rajapalayam",
            "South", 9.4457, 77.5568, "Nehru Nagar, Rajapalayam", 0.0),
        HospitalDestination("RJP-12", "Sakthi Nursing Home",
            "Gynaecology & Family Health", "Rajapalayam",
            "West", 9.4492, 77.5509, "Kambar St, Rajapalayam", 0.0),
        HospitalDestination("RJP-13", "Kavitha Hospital",
            "Dermatology & General Medicine", "Rajapalayam",
            "North", 9.4562, 77.5548, "Collectorate Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-14", "Sri Arunodhaya Hospital",
            "Cardiac & Intensive Care", "Rajapalayam",
            "East", 9.4479, 77.5615, "Bypass Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-15", "Rani Nursing Home",
            "Maternity & Women's Health", "Rajapalayam",
            "South", 9.4438, 77.5552, "Saradha Nagar, Rajapalayam", 0.0),
        HospitalDestination("RJP-16", "Annai Nursing Home",
            "Paediatrics & Child Care", "Rajapalayam",
            "North", 9.4575, 77.5500, "Gandhi Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-17", "Om Sakthi Hospital",
            "Neurology & Spine", "Rajapalayam",
            "West", 9.4510, 77.5492, "Sundaram Mills Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-18", "Prashanth Eye Hospital",
            "Ophthalmology & Vision Care", "Rajapalayam",
            "East", 9.4502, 77.5618, "Collector Office Rd, Rajapalayam", 0.0),
        HospitalDestination("RJP-19", "Vetri Dental & Maxillofacial",
            "Dental Surgery & Oral Care", "Rajapalayam",
            "South", 9.4445, 77.5528, "Big Bazaar St, Rajapalayam", 0.0),
        HospitalDestination("RJP-20", "Balaji Physiotherapy Centre",
            "Physiotherapy & Rehabilitation", "Rajapalayam",
            "North", 9.4588, 77.5516, "TNHB Colony, Rajapalayam", 0.0),
    )

    // ── Public API ────────────────────────────────────────────────────────────────────────────────

    /**
     * PRIMARY entry point.
     *
     * 1. Reverse-geocodes [lat],[lon] to discover the city/town/village name.
     * 2. Resolves that name to an OSM area ID via Nominatim.
     * 3. Queries Overpass for ALL hospitals/clinics/doctors/pharmacies inside that area.
     * 4. Sorts results by distance from [lat],[lon].
     * 5. Falls back to the curated Rajapalayam list on any failure.
     *
     * Returns a [Pair] of (cityName, hospitals) so the caller can display the city name.
     */
    suspend fun fetchByLocation(
        lat: Double,
        lon: Double,
    ): Pair<String, List<HospitalDestination>> = withContext(Dispatchers.IO) {
        try {
            // Step 1 – detect city name from GPS
            val cityName = reverseGeocode(lat, lon)
            if (cityName == null) {
                Log.w(TAG, "Reverse geocode failed for ($lat,$lon), using fallback")
                return@withContext "Rajapalayam" to withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
            }
            Log.d(TAG, "Detected city: $cityName for ($lat,$lon)")

            // Step 2 – resolve city to OSM area ID
            val areaId = resolveAreaId(cityName)
            if (areaId == null) {
                Log.w(TAG, "Could not resolve OSM area for '$cityName', using fallback")
                return@withContext cityName to withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
            }

            // Step 3 – fetch all hospitals in that city boundary
            val hospitals = fetchHospitalsInArea(areaId, lat, lon, cityName)
            if (hospitals.isEmpty()) {
                Log.w(TAG, "No hospitals found in '$cityName', using fallback")
                return@withContext cityName to withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
            }

            Log.d(TAG, "Fetched ${hospitals.size} hospitals in $cityName")
            cityName to hospitals.sortedBy { it.distanceKm }
        } catch (e: Exception) {
            Log.e(TAG, "fetchByLocation failed: ${e.message}")
            "Unknown" to withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
        }
    }

    /**
     * Named-city fetch — used when the driver manually changes the city via the UI.
     */
    suspend fun fetchByCity(
        lat: Double,
        lon: Double,
        cityName: String,
    ): List<HospitalDestination> = withContext(Dispatchers.IO) {
        try {
            val areaId = resolveAreaId(cityName)
                ?: return@withContext withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
            val hospitals = fetchHospitalsInArea(areaId, lat, lon, cityName)
            if (hospitals.isEmpty()) withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
            else hospitals.sortedBy { it.distanceKm }
        } catch (e: Exception) {
            Log.e(TAG, "fetchByCity failed: ${e.message}")
            withDistances(RAJAPALAYAM_FALLBACK, lat, lon)
        }
    }

    // ── Reverse geocoding ─────────────────────────────────────────────────────────────────────────

    /**
     * Convert [lat],[lon] → city/town/village name using Nominatim reverse geocoding.
     *
     * Priority order for address components (most specific to least):
     *   city → town → village → county → state_district
     *
     * Returns null if the network call fails or no usable name is found.
     */
    fun reverseGeocode(lat: Double, lon: Double): String? {
        return try {
            val url = URL(
                "$NOMINATIM_URL/reverse" +
                    "?lat=$lat&lon=$lon&format=json&zoom=10&addressdetails=1"
            )
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "LifeLane-Ambulance-App/1.0")
            conn.connectTimeout = 8_000
            conn.readTimeout    = 10_000

            if (conn.responseCode != 200) {
                Log.w(TAG, "Nominatim reverse HTTP ${conn.responseCode}")
                return null
            }

            val json    = conn.inputStream.bufferedReader().readText()
            val root    = JSONObject(json)
            val address = root.optJSONObject("address") ?: return null

            // Pick the most precise populated-place level available
            val city = address.optString("city", "")
                .ifBlank { address.optString("town", "") }
                .ifBlank { address.optString("village", "") }
                .ifBlank { address.optString("suburb", "") }
                .ifBlank { address.optString("county", "") }
                .ifBlank { address.optString("state_district", "") }
                .trim()

            if (city.isBlank()) {
                Log.w(TAG, "No city-level name found in reverse geocode response")
                null
            } else {
                Log.d(TAG, "reverseGeocode($lat,$lon) → $city")
                city
            }
        } catch (e: Exception) {
            Log.e(TAG, "reverseGeocode failed: ${e.message}")
            null
        }
    }

    // ── Area ID resolution ────────────────────────────────────────────────────────────────────────

    /**
     * Resolve a city name → OSM area ID via Nominatim forward search.
     * Overpass area IDs:  relation → +3_600_000_000,  way → +2_400_000_000.
     */
    private fun resolveAreaId(cityName: String): Long? {
        return try {
            val encoded = java.net.URLEncoder.encode(cityName, "UTF-8")
            val url = URL(
                "$NOMINATIM_URL/search" +
                    "?q=$encoded&format=json&limit=5&addressdetails=1"
            )
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "LifeLane-Ambulance-App/1.0")
            conn.connectTimeout = 8_000
            conn.readTimeout    = 10_000

            if (conn.responseCode != 200) return null

            val json = conn.inputStream.bufferedReader().readText()
            val arr  = org.json.JSONArray(json)

            for (i in 0 until arr.length()) {
                val obj     = arr.getJSONObject(i)
                val osmType = obj.optString("osm_type", "")
                val osmId   = obj.optLong("osm_id", -1L)
                if (osmId < 0) continue

                val areaId = when (osmType) {
                    "relation" -> 3_600_000_000L + osmId
                    "way"      -> 2_400_000_000L + osmId
                    "node"     -> osmId
                    else       -> continue
                }
                Log.d(TAG, "resolveAreaId('$cityName') → $osmType $osmId → area $areaId")
                return areaId
            }
            null
        } catch (e: Exception) {
            Log.e(TAG, "resolveAreaId failed: ${e.message}")
            null
        }
    }

    // ── Overpass query ────────────────────────────────────────────────────────────────────────────

    private fun fetchHospitalsInArea(
        areaId:    Long,
        originLat: Double,
        originLon: Double,
        cityName:  String,
    ): List<HospitalDestination> {
        val query = """
            [out:json][timeout:25];
            area($areaId)->.searchArea;
            (
              node["amenity"~"^(hospital|clinic|doctors|pharmacy)${'$'}"](area.searchArea);
              way["amenity"~"^(hospital|clinic|doctors|pharmacy)${'$'}"](area.searchArea);
              relation["amenity"~"^(hospital|clinic|doctors|pharmacy)${'$'}"](area.searchArea);
            );
            out center tags;
        """.trimIndent()

        val conn = (URL(OVERPASS_URL).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            doOutput      = true
            connectTimeout = 15_000
            readTimeout    = 30_000
        }
        conn.outputStream.use {
            it.write("data=${java.net.URLEncoder.encode(query, "UTF-8")}".toByteArray())
        }

        if (conn.responseCode != 200) {
            Log.w(TAG, "Overpass HTTP ${conn.responseCode}")
            return emptyList()
        }

        return parseOverpassResult(
            conn.inputStream.bufferedReader().readText(),
            originLat, originLon, cityName,
        )
    }

    // ── JSON parser ───────────────────────────────────────────────────────────────────────────────

    private fun parseOverpassResult(
        json:      String,
        originLat: Double,
        originLon: Double,
        cityName:  String,
    ): List<HospitalDestination> {
        val result = mutableListOf<HospitalDestination>()
        return try {
            val elements  = JSONObject(json).getJSONArray("elements")
            var idCounter = 1

            for (i in 0 until elements.length()) {
                val elem = elements.getJSONObject(i)
                val tags = elem.optJSONObject("tags") ?: continue

                val name = tags.optString("name", "").trim()
                if (name.isBlank()) continue

                val lat = when {
                    elem.has("lat")    -> elem.getDouble("lat")
                    elem.has("center") -> elem.getJSONObject("center").getDouble("lat")
                    else               -> continue
                }
                val lon = when {
                    elem.has("lon")    -> elem.getDouble("lon")
                    elem.has("center") -> elem.getJSONObject("center").getDouble("lon")
                    else               -> continue
                }

                val amenity   = tags.optString("amenity", "hospital")
                val specialty = when (amenity) {
                    "clinic"   -> tags.optString("healthcare:speciality", "Medical Clinic")
                        .replaceFirstChar(Char::uppercase).ifBlank { "Medical Clinic" }
                    "doctors"  -> "General Practitioner"
                    "pharmacy" -> "Pharmacy"
                    else       -> tags.optString(
                        "healthcare:speciality",
                        tags.optString("speciality", "General Hospital"),
                    ).replaceFirstChar(Char::uppercase).ifBlank { "General Hospital" }
                }

                val address = buildString {
                    val street = tags.optString("addr:street", "")
                    val city   = tags.optString("addr:city",
                                     tags.optString("addr:place", cityName))
                    if (street.isNotBlank()) append(street)
                    if (city.isNotBlank()) { if (isNotBlank()) append(", "); append(city) }
                    if (isBlank()) append("${name.take(20)}, $cityName")
                }

                result.add(
                    HospitalDestination(
                        id               = "OSM-${idCounter++}",
                        name             = name,
                        specialty        = specialty.take(48),
                        cityName         = cityName,
                        corridorApproach = bearingApproach(originLat, originLon, lat, lon),
                        latitude         = lat,
                        longitude        = lon,
                        address          = address.take(60),
                        distanceKm       = haversineKm(originLat, originLon, lat, lon),
                    )
                )
            }
            result
        } catch (e: Exception) {
            Log.e(TAG, "parseOverpassResult: ${e.message}")
            result
        }
    }

    // ── Utilities ─────────────────────────────────────────────────────────────────────────────────

    fun withDistances(
        list: List<HospitalDestination>,
        lat: Double,
        lon: Double,
    ) = list.map { h ->
        h.copy(
            distanceKm       = haversineKm(lat, lon, h.latitude, h.longitude),
            corridorApproach = bearingApproach(lat, lon, h.latitude, h.longitude),
        )
    }.sortedBy { it.distanceKm }

    private fun haversineKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val r  = 6_371.0
        val p1 = Math.toRadians(lat1); val p2 = Math.toRadians(lat2)
        val dp = Math.toRadians(lat2 - lat1); val dl = Math.toRadians(lon2 - lon1)
        val a  = sin(dp / 2).pow(2) + cos(p1) * cos(p2) * sin(dl / 2).pow(2)
        return r * 2 * atan2(sqrt(a), sqrt(1 - a))
    }

    private fun bearingApproach(fromLat: Double, fromLon: Double, toLat: Double, toLon: Double): String {
        val p1 = Math.toRadians(fromLat); val p2 = Math.toRadians(toLat)
        val dl = Math.toRadians(toLon - fromLon)
        val x  = sin(dl) * cos(p2)
        val y  = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl)
        val bearing = (Math.toDegrees(atan2(x, y)) + 360) % 360
        return when {
            bearing >= 337.5 || bearing < 22.5 -> "North"
            bearing < 67.5  -> "North-East"
            bearing < 112.5 -> "East"
            bearing < 157.5 -> "South-East"
            bearing < 202.5 -> "South"
            bearing < 247.5 -> "South-West"
            bearing < 292.5 -> "West"
            else            -> "North-West"
        }
    }
}
