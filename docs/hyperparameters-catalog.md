# Confluence — Hyperparameters & Scientific Metrics Catalog

This document provides a comprehensive, field-by-field reference of **all 75 raw scientific hyperparameters, 38 physics-derived metrics, 5 historical trend deltas, and 11 safety rules** processed by the Confluence platform.

---

## Metric Summary & Data Architecture

```
Confluence Environmental Snapshot (196 Total Response Leaves)
├── 75 Raw Scientific Hyperparameters (10 Independent Upstream Feeds)
│   ├── Open-Meteo Weather: 15 parameters
│   ├── Open-Meteo Marine: 13 parameters
│   ├── OpenAQ Ground Sensor Array: 9 parameters
│   ├── Sunrise-Sunset.org Ephemeris: 10 parameters
│   ├── Open-Meteo Elevation / Topography: 2 parameters
│   ├── NASA POWER Climatology Baseline: 3 parameters
│   ├── USGS Earthquake Hazards: 5 parameters
│   ├── Copernicus GloFAS River Flood: 4 parameters
│   ├── GDACS Tropical Cyclone Tracking: 7 parameters
│   └── NASA FIRMS Satellite Fire Anomalies: 7 parameters
│
├── 38 Physics-Informed Derived Metrics (16 High-Level Composite Signals)
│   ├── Physiological Heat Index: 2 metrics
│   ├── Condensation & Fog Visibility: 2 metrics
│   ├── WMO Beaufort Wind Force: 2 metrics
│   ├── IMD Tropical System Scale: 1 metric
│   ├── NWS Small Craft Advisory & Sea State: 3 metrics
│   ├── Storm Potential & Convective Tendency: 2 metrics
│   ├── Latitude-Normalized Rapid Pressure Fall: 3 metrics
│   ├── EPA / NOAA Air Stagnation Index: 1 metric
│   ├── Coastal & Estuarine Flood Risk: 5 metrics
│   ├── Nearshore Seismic & Tsunami Advisory: 2 metrics
│   ├── Tropical Cyclone Proximity Tracking: 8 metrics
│   └── NASA FIRMS Smoke / Fire Causality: 6 metrics
│
├── 5 Historical 24-Hour Trend Differentials (Durable MongoDB Storage)
│   └── ΔT (°C), ΔP (hPa), ΔRH (%), ΔPM2.5 (µg/m³), ΔWaveHeight (m)
│
└── 11 Multi-Hazard Safety Alert Rules (Rules Engine)
    └── Small craft, Gale, Storm, Heat danger, Air hazard, AQ spike, 
        Rapid pressure fall, Estuarine compound flood, Cyclone, Tsunami, Stagnation
```

---

## 1. Raw Hyperparameters Catalog (75 Parameters Across 10 Feeds)

### Domain 1: Open-Meteo Weather (15 Parameters)
* **Provider:** Open-Meteo Weather API
* **Endpoint:** `https://api.open-meteo.com/v1/forecast`
* **Update Frequency:** Hourly numerical model assimilation (ECMWF IFS / DWD ICON)

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `temperature_c` | `float` | °C | $-50.0$ to $60.0$ | Ambient surface air temperature at 2m above ground level |
| `apparent_temperature_c` | `float` | °C | $-60.0$ to $75.0$ | Perceived temperature combining wind chill and relative humidity |
| `wind_speed_kmh` | `float` | km/h | $\ge 0.0$ | Sustained surface horizontal wind velocity at 10m |
| `wind_gusts_kmh` | `float` | km/h | $\ge 0.0$ | Maximum 3-second peak wind gust velocity at 10m |
| `wind_direction_deg` | `int` | degrees | $0$ to $360$ | Meteorological wind direction (direction wind blows from, 0°=North) |
| `humidity_pct` | `int` | % | $0$ to $100$ | Relative humidity of air at 2m |
| `pressure_hpa` | `float` | hPa | $870.0$ to $1085.0$ | Atmospheric air pressure adjusted to Mean Sea Level (MSL) |
| `surface_pressure_hpa` | `float` | hPa | $850.0$ to $1090.0$ | True local barometric pressure at ground surface elevation |
| `precipitation_mm` | `float` | mm | $\ge 0.0$ | Liquid water equivalent precipitation accumulated over current hour |
| `cloud_cover_pct` | `int` | % | $0$ to $100$ | Total sky cloud coverage fraction |
| `uv_index` | `float` | index | $0.0$ to $20.0+$ | Solar ultraviolet radiation intensity scale |
| `visibility_m` | `float` | meters | $\ge 0.0$ | Horizontal atmospheric visibility distance |
| `weather_code` | `int` | code | $0$ to $99$ | WMO standard numerical weather synoptic interpretation code |
| `weather_description` | `str` | text | Categorical | Plain-text translation of WMO code (e.g. "Mainly clear", "Thunderstorm") |
| `is_day` | `int` | flag | $0$ or $1$ | Solar diurnal indicator: 1 = daylight, 0 = night |

---

### Domain 2: Open-Meteo Marine Hydrodynamics (13 Parameters)
* **Provider:** Open-Meteo Marine API
* **Endpoint:** `https://marine-api.open-meteo.com/v1/marine`
* **Update Frequency:** 1-to-3 hour ocean model runs (Copernicus Marine Mercator / NOAA GFS-Wave)

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `sea_surface_temp_c` | `float` | °C | $-2.5$ to $45.0$ | Ocean skin water temperature at the surface layer |
| `wave_height_m` | `float` | meters | $\ge 0.0$ | Significant wave height ($H_{1/3}$, mean of highest one-third of waves) |
| `wave_period_s` | `float` | seconds | $\ge 0.0$ | Peak wave period between consecutive wave crests |
| `wave_direction_deg` | `int` | degrees | $0$ to $360$ | Mean direction from which overall combined waves are propagating |
| `wind_wave_height_m` | `float` | meters | $\ge 0.0$ | Locally generated wind-sea wave height fraction |
| `wind_wave_period_s` | `float` | seconds | $\ge 0.0$ | Period of locally forced wind waves |
| `wind_wave_direction_deg` | `int` | degrees | $0$ to $360$ | Direction of locally generated wind waves |
| `swell_wave_height_m` | `float` | meters | $\ge 0.0$ | Significant height of remotely generated ocean swell |
| `swell_wave_period_s` | `float` | seconds | $\ge 0.0$ | Period of long-wavelength ocean swell waves |
| `swell_wave_direction_deg`| `int` | degrees | $0$ to $360$ | Direction of incoming deep-water ocean swell |
| `ocean_current_velocity_kmh` | `float` | km/h | $\ge 0.0$ | Speed of horizontal ocean surface water drift velocity |
| `ocean_current_direction_deg`| `int` | degrees | $0$ to $360$ | Direction toward which ocean surface current is flowing |
| `note` | `str` | text | Informational | Provenance or coastal boundary interpolation disclaimer |

---

### Domain 3: OpenAQ Ground Station Sensor Array (9 Parameters)
* **Provider:** OpenAQ API v3 (Physical Ground Nodes) with Open-Meteo CAMS Fallback
* **Endpoint:** `https://api.openaq.org/v3/locations` / `https://air-quality-api.open-meteo.com/v1/air-quality`
* **Update Frequency:** Real-time / hourly ground telemetry from regulatory stations (CPCB / TNPCB / MPCB)

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `station_name` | `str` | text | Alphanumeric | Name and agency of nearest physical monitoring station node |
| `data_type` | `str` | enum | `measured` / `modeled` | Provenance tag: `measured` (physical sensor) or `modeled` (CAMS) |
| `pm25` | `float` | µg/m³ | $\ge 0.0$ | Fine particulate matter concentration ($<2.5\ \mu\text{m}$) |
| `pm10` | `float` | µg/m³ | $\ge 0.0$ | Coarse inhalable particulate matter concentration ($<10\ \mu\text{m}$) |
| `o3` | `float` | µg/m³ | $\ge 0.0$ | Tropospheric surface ozone concentration |
| `no2` | `float` | µg/m³ | $\ge 0.0$ | Nitrogen dioxide gaseous concentration |
| `so2` | `float` | µg/m³ | $\ge 0.0$ | Sulfur dioxide gaseous emission concentration |
| `co` | `float` | µg/m³ | $\ge 0.0$ | Carbon monoxide airborne concentration |
| `aqi_category` | `str` | enum | CPCB / US EPA tiers | Qualitative air quality index category (Good, Moderate, Unhealthy, etc.) |

---

### Domain 4: Sunrise-Sunset Marine Ephemeris (10 Parameters)
* **Provider:** Sunrise-Sunset.org API
* **Endpoint:** `https://api.sunrise-sunset.org/json`
* **Update Frequency:** Daily astronomical orbital calculations

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `sunrise` | `str` | UTC ISO-8601 | Timestamp | Moment upper edge of solar disk appears above horizon |
| `sunset` | `str` | UTC ISO-8601 | Timestamp | Moment solar disk completely disappears below horizon |
| `solar_noon` | `str` | UTC ISO-8601 | Timestamp | Point of maximum solar elevation and zenith |
| `day_length_hours` | `float` | hours | $0.0$ to $24.0$ | Total daylight duration between sunrise and sunset |
| `civil_twilight_begin` | `str` | UTC ISO-8601 | Timestamp | Sun is 6° below horizon (adequate natural light for outdoor activities) |
| `civil_twilight_end` | `str` | UTC ISO-8601 | Timestamp | End of civil twilight; artificial harbor lighting required |
| `nautical_twilight_begin` | `str` | UTC ISO-8601 | Timestamp | Sun is 12° below horizon (seafaring horizon becomes distinguishable) |
| `nautical_twilight_end` | `str` | UTC ISO-8601 | Timestamp | Full navigational darkness for maritime vessels |
| `astronomical_twilight_begin` | `str` | UTC ISO-8601 | Timestamp | Sun is 18° below horizon; sky illumination begins |
| `astronomical_twilight_end` | `str` | UTC ISO-8601 | Timestamp | Complete astronomical darkness |

---

### Domain 5: Open-Meteo Elevation & Coastal Topography (2 Parameters)
* **Provider:** Open-Meteo Elevation API (Shuttle Radar Topography Mission / ASTER DEM)
* **Endpoint:** `https://api.open-meteo.com/v1/elevation`

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `elevation_m` | `float` | meters | $-500.0$ to $9000.0$ | Terrain height above Mean Sea Level (critical for storm surge runup) |
| `coastal_risk_category` | `str` | enum | Low / Moderate / High | Topographic vulnerability classification based on low elevation ($<5\text{m}$) |

---

### Domain 6: NASA POWER Climatological Baseline (3 Parameters)
* **Provider:** NASA Prediction Of Worldwide Energy Resources (POWER)
* **Endpoint:** `https://power.larc.nasa.gov/api/temporal/daily/point`

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `solar_radiation_kwh_m2` | `float` | kWh/m²/day | $\ge 0.0$ | All-sky surface shortwave solar downward irradiance |
| `avg_temperature_c` | `float` | °C | Climatological Mean | Multi-year historical baseline temperature for the seasonal period |
| `avg_wind_speed_ms` | `float` | m/s | $\ge 0.0$ | Multi-year climatological normal wind velocity baseline |

---

### Domain 7: USGS Seismic Hazards & Tsunami Watch (5 Parameters)
* **Provider:** USGS Earthquake Hazards Program
* **Endpoint:** `https://earthquake.usgs.gov/fdsnws/event/1/query`
* **Update Frequency:** Real-time global seismic feeds

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `recent_events_7d_count` | `int` | count | $\ge 0$ | Total recorded earthquakes ($M \ge 4.0$) within regional search radius |
| `max_magnitude` | `float` | Richter/Mw | $\ge 0.0$ or `None` | Peak earthquake magnitude observed in past 7 days within 500km |
| `max_magnitude_depth_km` | `float` | kilometers | $\ge 0.0$ or `None` | Focal depth of the peak earthquake ($<70\text{km}$ = shallow focus) |
| `hazard_level` | `str` | enum | Nominal / Elevated | Seismic hazard evaluation for low-lying coastal margin |
| `search_radius_km` | `float` | kilometers | $500.0$ | Fixed spatial evaluation radius around coordinate |

---

### Domain 8: Copernicus GloFAS River Flood & Runoff (4 Parameters)
* **Provider:** Open-Meteo Flood API (Global Flood Awareness System)
* **Endpoint:** `https://flood-api.open-meteo.com/v1/flood`
* **Update Frequency:** Daily global hydrological river routing model runs

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `river_discharge_m3s` | `float` | m³/s | $\ge 0.0$ or `None` | Upstream river channel discharge rate for estuarine delta |
| `discharge_max_7d_m3s` | `float` | m³/s | $\ge 0.0$ or `None` | 7-day projected peak river discharge |
| `applicable` | `bool` | flag | `True` / `False` | Whether coordinate sits in an active river drainage basin |
| `note` | `str` | text | Informational | River basin attribution or non-basin oceanic notice |

---

### Domain 9: GDACS Tropical Cyclone Tracking (7 Parameters)
* **Provider:** Global Disaster Alert and Coordination System (UN OCHA / European Commission JRC)
* **Endpoint:** `https://www.gdacs.org/xml/rss.xml`
* **Update Frequency:** Real-time satellite & meteorological tracking feeds

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `active_cyclone_nearby` | `bool` | flag | `True` / `False` | True if an active named tropical system is within regional maritime range |
| `nearest_cyclone_name` | `str` | text | Name or `None` | Official international storm identifier (e.g. "TC REMAL") |
| `nearest_cyclone_distance_km`| `float` | kilometers | $\ge 0.0$ or `None` | Geodesic Haversine distance to active cyclone center |
| `cyclone_alert_level` | `str` | enum | Green / Orange / Red | GDACS international disaster alert impact classification |
| `max_wind_speed_kmh` | `float` | km/h | $\ge 0.0$ or `None` | Maximum sustained surface wind speed reported for the storm |
| `active_cyclones_count` | `int` | count | $\ge 0$ | Total number of active tropical depressions / cyclones in basin |
| `nearby_cyclones` | `list` | objects | Array | List of structured records for all systems within monitoring range |

---

### Domain 10: NASA FIRMS Satellite Active Fire & Thermal Anomalies (7 Parameters)
* **Provider:** NASA FIRMS (MODIS / VIIRS Sensor Telemetry)
* **Endpoint:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv`
* **Update Frequency:** Near-Real-Time (NRT) satellite passes (every 3 to 12 hours)

| Field Name | Type | Unit | Range / Format | Description |
| :--- | :---: | :---: | :---: | :--- |
| `hotspot_count` | `int` | count | $\ge 0$ | Total satellite thermal anomalies detected within 300km radius |
| `high_confidence_count` | `int` | count | $\ge 0$ | High-confidence thermal detection count (filters out solar reflections) |
| `fire_detected` | `bool` | flag | `True` / `False` | Physical flag indicating active thermal hotspots present |
| `nearest_hotspot_distance_km`| `float` | kilometers | $\ge 0.0$ or `None` | Distance to closest satellite fire detection |
| `max_frp_mw` | `float` | MegaWatts | $\ge 0.0$ or `None` | Peak Fire Radiative Power (MW), measuring biomass combustion intensity |
| `search_radius_km` | `float` | kilometers | $300.0$ | Geospatial causality search radius |
| `sample_hotspots` | `list` | objects | Array | Coordinates, FRP, and satellite instrument metadata for top fires |

---

## 2. The 38 Derived Physics Leaf Metrics

Computed deterministically on the server in [`backend/derived_insights.py`](file:///c:/Users/cshar/Desktop/Confluence/backend/derived_insights.py):

| Derived Metric Key | Type | Unit / Enum | Source Standard | Physical Description |
| :--- | :---: | :---: | :--- | :--- |
| `heat_index_c` | `float` | °C | NOAA / Rothfusz | Apparent temperature accounting for evaporative cooling inhibition |
| `heat_index_category` | `str` | normal / caution / extreme_caution / danger / extreme_danger | NOAA NWS | Physiological heat stress risk tier |
| `dew_point_c` | `float` | °C | Magnus-Tetens (WMO) | Temperature at which water vapor condenses into liquid |
| `fog_risk` | `str` | low / moderate / high / unknown | WMO Aviation | Surface fog formation likelihood from dew point spread and wind |
| `beaufort_scale.force` | `int` | $0$ to $12$ | WMO-No. 558 | International empirical wind force integer |
| `beaufort_scale.name` | `str` | text | WMO-No. 558 | Standard nautical wind force description (e.g. "Gale", "Strong breeze") |
| `imd_cyclone_category` | `str` | IMD 7-tier scale | IMD RSMC | Official Indian Ocean tropical disturbance classification |
| `small_craft_risk_level` | `str` | none / small_craft_advisory / gale_warning / storm_warning / hurricane_force_warning / critical | NOAA NWS Directive 10-303 | Primary coastal maritime safety rating for small vessels |
| `small_craft_risk_detail.level` | `str` | enum | NOAA NWS | Verified warning level code |
| `small_craft_risk_detail.wind_kmh_used` | `float` | km/h | NOAA NWS | Worst-case wind speed (sustained vs gusts) used in calculation |
| `small_craft_risk_detail.wave_height_m_used` | `float` | meters | NOAA NWS | Significant wave height used in sea-state warning evaluation |
| `storm_potential_score` | `float` | $0.00$ to $1.00$ | Barometric Index | Composite multi-factor convective squall indicator |
| `storm_potential_level` | `str` | low / moderate / high / severe | Convective Tier | Qualitative storm potential tier |
| `rapid_pressure_fall.change_24h_hpa` | `float` | hPa | Historical Diff | Barometric change over past 24 hours |
| `rapid_pressure_fall.latitude_normalized_threshold_hpa` | `float` | hPa | Sanders-Gyakum (1980) | Latitude-scaled explosive cyclogenesis threshold |
| `rapid_pressure_fall.rapid_fall` | `bool` | `True` / `False` | Sanders-Gyakum | Flags rapid barometric deepening requiring synoptic watch |
| `air_stagnation_index` | `str` | low / moderate / high | US EPA / NOAA | Identifies atmospheric boundary layer inversion and trapping |
| `coastal_flood_risk.score` | `float` | $0.00$ to $1.00$ | Composite | Combined elevation, wave, wind, surge, and river runoff exposure |
| `coastal_flood_risk.level` | `str` | low / moderate / high / severe | Inundation Tier | Qualitative coastal flood hazard tier |
| `coastal_flood_risk.inverse_barometer_surge_cm` | `float` | cm | Pugh & Woodworth (2014) | Static sea surface elevation rise from atmospheric pressure deficit |
| `coastal_flood_risk.river_discharge_m3s` | `float` | m³/s | Copernicus GloFAS | Upstream river flow contributing to deltaic flood stage |
| `coastal_flood_risk.estuarine_compound_risk` | `bool` | `True` / `False` | Estuarine Hydrology | Critical flag when high river flow collides with marine surge |
| `tsunami_advisory.advisory` | `bool` | `True` / `False` | USGS / PTWC | Flags dangerous nearshore shallow seismic displacement |
| `tsunami_advisory.reason` | `str` | text or `None` | USGS / PTWC | Explicit physical justification (magnitude, depth, station elevation) |
| `cyclone_advisory.advisory` | `bool` | `True` / `False` | GDACS | Flags active tropical storm within maritime hazard zones |
| `cyclone_advisory.level` | `str` | nominal / caution / critical | GDACS / WMO | Distance-gated maritime risk tier ($<500\text{km}$ = critical) |
| `cyclone_advisory.active_nearby` | `bool` | `True` / `False` | GDACS | Proximity indicator |
| `cyclone_advisory.nearest_cyclone` | `str` | text or `None` | GDACS | Name of the approaching tropical cyclone system |
| `cyclone_advisory.distance_km` | `float` | kilometers | Haversine | True geodesic distance to active cyclone eye |
| `cyclone_advisory.wind_speed_kmh` | `float` | km/h | GDACS | Peak sustained winds inside the cyclone core |
| `cyclone_advisory.alert_level` | `str` | Green / Orange / Red | GDACS | International disaster severity alert level |
| `cyclone_advisory.reason` | `str` | text | GDACS | Human-readable operational safety advisory |
| `air_quality_causality.elevated_pm25` | `bool` | `True` / `False` | WHO / NAAQS | Flags PM2.5 exceeding the $35.4\ \mu\text{g}/\text{m}^3$ health standard |
| `air_quality_causality.biomass_burning_detected` | `bool` | `True` / `False` | NASA FIRMS | Satellite verification of active crop residue or biomass combustion |
| `air_quality_causality.hotspots_within_300km` | `int` | count | NASA FIRMS | Total satellite thermal anomaly count within 300km corridor |
| `air_quality_causality.nearest_hotspot_km` | `float` | kilometers | Haversine | Distance to closest satellite-detected fire node |
| `air_quality_causality.peak_frp_mw` | `float` | MegaWatts | NASA FIRMS | Maximum Fire Radiative Power observed |
| `air_quality_causality.causal_attribution` | `str` | text | Attribution Logic | Deterministic attribution distinguishing crop fires from urban traffic |

---

## 3. The 5 Historical Trend Differentials (24h Deltas)

Stored and retrieved from MongoDB Atlas / SQLite by [`backend/storage.py`](file:///c:/Users/cshar/Desktop/Confluence/backend/storage.py):

| Metric Key in `trend_24h` | Unit | Formula | Operational Significance |
| :--- | :---: | :---: | :--- |
| `temperature_c.diff` | °C | $T_{\text{current}} - T_{24\text{h ago}}$ | Frontal boundary passage or nocturnal inversion cooling |
| `pressure_hpa.diff` | hPa | $P_{\text{current}} - P_{24\text{h ago}}$ | 24-hour synoptic pressure trend (deepening vs filling) |
| `humidity_pct.diff` | % | $\text{RH}_{\text{current}} - \text{RH}_{24\text{h ago}}$ | Marine air mass advection / onshore moisture influx |
| `pm25.diff` | µg/m³ | $\text{PM2.5}_{\text{current}} - \text{PM2.5}_{24\text{h ago}}$ | Particulate pollution trend ($\ge 2\times$ triggers rapid spike alert) |
| `wave_height_m.diff` | meters | $H_{\text{current}} - H_{24\text{h ago}}$ | Incoming oceanic swell propagation from distant storms |

---

## 4. The 11 Multi-Hazard Rules Engine Alerts

Evaluated against thresholds and trends by [`backend/rules_engine.py`](file:///c:/Users/cshar/Desktop/Confluence/backend/rules_engine.py):

| Rule ID | Severity | Threshold Trigger Criteria |
| :--- | :---: | :--- |
| `small_craft_advisory` | `warning` | Sustained wind $\ge 33.3\text{ km/h}$ OR Wave height $\ge 2.1\text{ m}$ |
| `gale_warning` | `critical` | Sustained wind $\ge 63.0\text{ km/h}$ OR Wave height $\ge 3.5\text{ m}$ |
| `storm_warning` | `critical` | Sustained wind $\ge 88.9\text{ km/h}$ OR Wave height $\ge 5.5\text{ m}$ |
| `heat_index_danger` | `warning` | Computed Heat Index $\ge 39.4^\circ\text{C}$ ($103^\circ\text{F}$) |
| `air_quality_hazardous` | `critical` | PM2.5 concentration $\ge 150.4\ \mu\text{g}/\text{m}^3$ |
| `air_quality_spike_24h` | `warning` | Current PM2.5 $\ge 35.4\ \mu\text{g}/\text{m}^3$ AND $\ge 2.0 \times$ reading from 24 hours ago |
| `rapid_pressure_drop_3h` | `warning` | Barometric pressure drop $\ge 3.0\text{ hPa}$ within a 3-hour window |
| `compound_estuarine_flood` | `critical` | River discharge $\ge 20\text{ m}^3/\text{s}$ + Marine Forcing (surge/wave/wind) + Elev $<10\text{ m}$ |
| `tropical_cyclone_proximity`| `critical` | Active named tropical cyclone system within $\le 500\text{ km}$ geodesic radius |
| `tsunami_caution` | `critical` | Offshore earthquake $M \ge 6.5$ with shallow focus ($<70\text{km}$) + Elev $<10\text{ m}$ |
| `air_stagnation_high` | `advisory` | Wind $<10\text{ km/h}$ + Rain $<0.5\text{ mm}$ + PM2.5 $>35.4\ \mu\text{g}/\text{m}^3$ |
