#include <Arduino.h>

// --- DEFINISI PIN ---
const int K1 = 3; // Inlet
const int K2 = 4; // Exhaust
const int K3 = 5; // Condensate
const int K4 = 6; // Pompa
const int SENSOR_PIN = A0;
const int ON = LOW;
const int OFF = HIGH;

// --- KALIBRASI SENSOR (VIRTUAL ZERO) ---
const float RAW_0_BAR = 116.3;
const float ADC_PER_BAR = 73.3;

// --- TUNING KOMPENSASI VOLTAGE DROP ---
const float COMP_K1 = 7.1; // Inlet
const float COMP_K2 = 7.3; // Exhaust
const float COMP_K3 = 7.2; // Condensate
const float COMP_K4 = 7.3; // Pompa

// --- KONFIGURASI WAKTU ---
const unsigned long RELEASE_DELAY_MS = 2000; // Jeda 2 Detik saat di 0.00
const int HOLDING_TIME_SEC = 45; // Waktu Holding diperpanjang jadi 45 detik

// Variabel Global Sistem
bool isAutoRunning = false;
int currentStep = 0;
unsigned long stepStartTime = 0;
unsigned long lastUpdate = 0;
unsigned long stabilityStartTime = 0;

// Status Relay
bool s1 = false, s2 = false, s3 = false, s4 = false;

void updateRelays() {
  digitalWrite(K1, s1 ? ON : OFF);
  digitalWrite(K2, s2 ? ON : OFF);
  digitalWrite(K3, s3 ? ON : OFF);
  digitalWrite(K4, s4 ? ON : OFF);
}

// --- FUNGSI BACA SENSOR ---
float getPressureFiltered() {
  const int sampleSize = 25;
  int rawReadings[sampleSize];

  for (int i = 0; i < sampleSize; i++) {
    rawReadings[i] = analogRead(SENSOR_PIN);
    delayMicroseconds(50);
  }

  // Median Filter
  for (int i = 0; i < sampleSize - 1; i++) {
    for (int j = i + 1; j < sampleSize; j++) {
      if (rawReadings[i] > rawReadings[j]) {
        int temp = rawReadings[i];
        rawReadings[i] = rawReadings[j];
        rawReadings[j] = temp;
      }
    }
  }

  // Rata-rata
  long sumMedian = 0;
  for (int i = 10; i < 15; i++) sumMedian += rawReadings[i];
  float rawAvg = sumMedian / 5.0;

  // Kompensasi Voltage Drop (Perbaikan typo totalOƯset menjadi totalOffset)
  float totalOffset = 0;
  if (s1) totalOffset += COMP_K1;
  if (s2) totalOffset += COMP_K2;
  if (s3) totalOffset += COMP_K3;
  if (s4) totalOffset += COMP_K4;

  float rawFinal = rawAvg - totalOffset;

  // Konversi ke Bar
  float p = (rawFinal - RAW_0_BAR) / ADC_PER_BAR;

  // CLAMPING
  return (p < 0) ? 0 : p;
}

void setup() {
  Serial.begin(115200);
  pinMode(K1, OUTPUT);
  pinMode(K2, OUTPUT);
  pinMode(K3, OUTPUT);
  pinMode(K4, OUTPUT);
  s1 = s2 = s3 = s4 = false;
  updateRelays();

  Serial.println("SYSTEM READY: HOLDING REFILL 1.00 - 1.15");
}

void loop() {
  float p = getPressureFiltered();

  // --- SERIAL REPORTING ---
  if (millis() - lastUpdate >= 500) {
    Serial.print(p, 2);
    Serial.print(",");
    if (!isAutoRunning) {
      if (s2 && s3) Serial.println("EMERGENCY RELEASE");
      else if (s1 || s4) Serial.println("MANUAL RUN");
      else Serial.println("STANDBY");
    } else {
      Serial.print("STEP ");
      Serial.println(currentStep);
    }
    lastUpdate = millis();
  }

  // --- LOGIKA OTOMASI ---
  if (isAutoRunning) {
    unsigned long elapsed = (millis() - stepStartTime) / 1000;
    switch (currentStep) {
      case 1: // TAHAP 1: PEAK 0.4 BAR
        s1 = true; s2 = false; s3 = false; s4 = true;
        if (p >= 0.40) {
          currentStep = 2; stepStartTime = millis(); stabilityStartTime = 0;
        }
        break;

      case 2: // RELEASE 1 (JEDA 2 DETIK DI 0)
        s1 = false; s2 = true; s3 = false; s4 = false;
        if (p <= 0.001) {
          if (stabilityStartTime == 0) stabilityStartTime = millis();
          if (millis() - stabilityStartTime > RELEASE_DELAY_MS) {
            currentStep = 3; stepStartTime = millis(); stabilityStartTime = 0;
          }
        } else {
          stabilityStartTime = 0;
        }
        break;

      case 3: // TAHAP 2: PEAK 0.7 BAR
        s1 = true; s2 = false; s3 = false; s4 = true;
        if (p >= 0.70) {
          currentStep = 4; stepStartTime = millis(); stabilityStartTime = 0;
        }
        break;

      case 4: // RELEASE 2 (JEDA 2 DETIK DI 0)
        s1 = false; s2 = true; s3 = false; s4 = false;
        if (p <= 0.001) {
          if (stabilityStartTime == 0) stabilityStartTime = millis();
          if (millis() - stabilityStartTime > RELEASE_DELAY_MS) {
            currentStep = 5; stepStartTime = millis(); stabilityStartTime = 0;
          }
        } else {
          stabilityStartTime = 0;
        }
        break;

      case 5: // TAHAP 3: PEAK 1.1 BAR
        s1 = true; s2 = false; s3 = false; s4 = true;
        if (p >= 1.10) {
          s1 = false; s4 = false; updateRelays();
          currentStep = 6; stepStartTime = millis(); stabilityStartTime = 0;
        }
        break;

      case 6: // TAHAP 4: HOLDING 45 DETIK + AUTO REFILL (Sempurna 1.03 - 1.10)
        if (elapsed >= HOLDING_TIME_SEC) {
          currentStep = 7; 
          stepStartTime = millis();
        } else {
          // --- LOGIKA PRESISI TINGGI ---
          
          // 1. Batas Bawah: Jika menyentuh 1.04, aktifkan pengisian
          // Ini mencegah tekanan drop di bawah 1.03 karena jeda mekanis.
          if (p <= 1.04) {
            s1 = true; 
            s4 = true;
          } 
          
          // 2. Batas Atas: Jika menyentuh 1.09, matikan segera.
          // Ini mencegah overshoot ke atas 1.10 akibat inersia tekanan.
          else if (p >= 1.09) {
            s1 = false; 
            s4 = false;
          }

          // 3. Emergency Cut-off: Jika karena alasan teknis tekanan tembus 1.10
          if (p >= 1.10) {
            s1 = false; 
            s4 = false;
          }

          s2 = false; // Pastikan Exhaust Tutup
          s3 = false; // Pastikan Condensate Tutup
        }
        break;

      case 7: // TAHAP 5: FINAL RELEASE
        s1 = false; s2 = true; s3 = true; s4 = false;
        if (p <= 0.001) {
          if (stabilityStartTime == 0) stabilityStartTime = millis();
          if (millis() - stabilityStartTime > 8000) {
            isAutoRunning = false; s1 = s2 = s3 = s4 = false;
          }
        } else {
          stabilityStartTime = 0;
        }
        break;
    }
    updateRelays();
  }

  // --- MANUAL COMMAND ---
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "1") { s1 = !s1; updateRelays(); }
    else if (cmd == "2") { s2 = !s2; updateRelays(); }
    else if (cmd == "3") { s3 = !s3; updateRelays(); }
    else if (cmd == "4") { s4 = !s4; updateRelays(); }
    else if (cmd == "start") {
      isAutoRunning = true;
      currentStep = 1;
      stepStartTime = millis();
      stabilityStartTime = 0;
      Serial.println("START: HOLDING TOP-UP SYSTEM");
    } else if (cmd == "reset") {
      isAutoRunning = false;
      s1 = s4 = false; s2 = s3 = true;
      updateRelays();
    } else if (cmd == "stop") {
      isAutoRunning = false;
      s1 = s2 = s3 = s4 = false;
      updateRelays();
    }
  }
}