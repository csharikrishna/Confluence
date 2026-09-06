/**
 * Confluence Coastal Station Telemetry Module
 * Handles active station switching, coordinates display, and telemetry cards DOM synchronization.
 */

let currentStationName = 'Chennai Coast';

const STATION_DATA = {
  'Chennai Coast': {
    coords: 'Latitude 13.08° N, Longitude 80.27° E • Tamil Nadu, Bay of Bengal',
    wave: '0.78 m', swell: '0.60 m', period: '8.8 s', seaTemp: '30.6 °C', current: '1.1 km/h',
    temp: '31.5 °C', apparent: '36.0 °C', wind: '10.4 / 32.8 km/h', humidity: '64 %', pressure: '1005.7 hPa',
    pm25: '23.8 µg/m³', pm10: '51.8 µg/m³', aqi: 'Moderate', aqiClass: 'success', tier: 'Ground Sensor', station: 'Royapuram',
    heatIndex: '34.9°C (Caution)', hiClass: 'warning', sca: 'Safe (None)', scaClass: 'success', cyclone: 'Normal', flood: 'Low', trend: '-0.4 hPa'
  },
  'Visakhapatnam Coast': {
    coords: 'Latitude 17.69° N, Longitude 83.22° E • Andhra Pradesh, Eastern Seaboard',
    wave: '1.02 m', swell: '0.85 m', period: '9.2 s', seaTemp: '29.8 °C', current: '1.4 km/h',
    temp: '30.2 °C', apparent: '34.6 °C', wind: '14.8 / 28.5 km/h', humidity: '68 %', pressure: '1008.2 hPa',
    pm25: '38.4 µg/m³', pm10: '74.2 µg/m³', aqi: 'Moderate', aqiClass: 'success', tier: 'Ground Sensor', station: 'Gajuwaka',
    heatIndex: '33.2°C (Caution)', hiClass: 'warning', sca: 'Safe (None)', scaClass: 'success', cyclone: 'Normal', flood: 'Low', trend: '+0.2 hPa'
  },
  'Kochi Coast': {
    coords: 'Latitude 9.93° N, Longitude 76.26° E • Kerala, Arabian Sea',
    wave: '1.12 m', swell: '0.94 m', period: '9.4 s', seaTemp: '29.2 °C', current: '1.8 km/h',
    temp: '29.4 °C', apparent: '33.8 °C', wind: '12.6 / 24.0 km/h', humidity: '76 %', pressure: '1010.5 hPa',
    pm25: '18.2 µg/m³', pm10: '39.5 µg/m³', aqi: 'Good', aqiClass: 'success', tier: 'Ground Sensor', station: 'Vyttila',
    heatIndex: '32.8°C (Caution)', hiClass: 'warning', sca: 'Favorable', scaClass: 'success', cyclone: 'Normal', flood: 'Low', trend: '-0.1 hPa'
  },
  'Mumbai Coast': {
    coords: 'Latitude 18.94° N, Longitude 72.84° E • Maharashtra, Konkan Coast',
    wave: '1.38 m', swell: '1.15 m', period: '7.8 s', seaTemp: '28.8 °C', current: '2.1 km/h',
    temp: '29.8 °C', apparent: '34.2 °C', wind: '17.1 / 34.2 km/h', humidity: '72 %', pressure: '1009.4 hPa',
    pm25: '64.5 µg/m³', pm10: '112.0 µg/m³', aqi: 'Unhealthy for Sensitive', aqiClass: 'warning', tier: 'Ground Sensor', station: 'Colaba',
    heatIndex: '33.6°C (Caution)', hiClass: 'warning', sca: 'Small Craft Caution', scaClass: 'warning', cyclone: 'Normal', flood: 'Low', trend: '+0.5 hPa'
  },
  'Kolkata / Sundarbans Coast': {
    coords: 'Latitude 21.63° N, Longitude 88.15° E • West Bengal, Ganges Delta',
    wave: '0.92 m', swell: '0.70 m', period: '8.4 s', seaTemp: '30.1 °C', current: '2.4 km/h',
    temp: '32.1 °C', apparent: '38.4 °C', wind: '11.5 / 26.0 km/h', humidity: '78 %', pressure: '1004.8 hPa',
    pm25: '52.0 µg/m³', pm10: '98.5 µg/m³', aqi: 'Moderate', aqiClass: 'success', tier: 'Ground Sensor', station: 'Haldia',
    heatIndex: '39.8°C (Danger)', hiClass: 'danger', sca: 'Safe', scaClass: 'success', cyclone: 'Normal', flood: 'Moderate (Tidal)', trend: '-0.8 hPa'
  }
};

function switchStation(name, lat, lon, region) {
  currentStationName = name;

  // Update tab active state
  const buttons = document.querySelectorAll('.station-tab-btn');
  buttons.forEach(btn => {
    if (btn.textContent.includes(name.split('/')[0].trim())) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Update Summary Action Banner
  const bannerName = document.getElementById('summaryStationName');
  if (bannerName) bannerName.textContent = name + ' Monitoring Station';

  const data = STATION_DATA[name] || STATION_DATA['Chennai Coast'];
  const bannerCoords = document.getElementById('summaryStationCoords');
  if (bannerCoords) bannerCoords.textContent = data.coords;

  // Update Hydrodynamics Card
  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setEl('valWaveHeight', data.wave);
  setEl('valSwellHeight', data.swell);
  setEl('valWavePeriod', data.period);
  setEl('valSeaTemp', data.seaTemp);
  setEl('valCurrent', data.current);

  // Update Weather & Atmosphere Card
  setEl('valTemp', data.temp);
  setEl('valApparentTemp', data.apparent);
  setEl('valWind', data.wind);
  setEl('valHumidity', data.humidity);
  setEl('valPressure', data.pressure);

  // Update Air Quality Array Card
  setEl('valPm25', data.pm25);
  setEl('valPm10', data.pm10);
  const aqiEl = document.getElementById('valAqiCategory');
  if (aqiEl) {
    aqiEl.textContent = data.aqi;
    aqiEl.className = 'datapoint-value badge-val ' + data.aqiClass;
  }
  setEl('valAqTier', data.tier);
  setEl('valStationName', data.station);

  // Update Physics Derived Signals Card
  const hiEl = document.getElementById('valHeatIndex');
  if (hiEl) {
    hiEl.textContent = data.heatIndex;
    hiEl.className = 'datapoint-value badge-val ' + data.hiClass;
  }
  const scaEl = document.getElementById('valSca');
  if (scaEl) {
    scaEl.textContent = data.sca;
    scaEl.className = 'datapoint-value badge-val ' + data.scaClass;
  }
  setEl('valCyclone', data.cyclone);
  setEl('valFlood', data.flood);
  setEl('valPressureTrend', data.trend);
}

function askAboutCurrentStation() {
  if (typeof openChatDrawer === 'function') {
    openChatDrawer(`What are current marine and environmental conditions near ${currentStationName}?`);
  }
}
