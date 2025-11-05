// SAMD21 + MAX485 passive monitor for frame logging
// USB console: Serial (115200)
// RS-485 bus:  Serial1 (configurable baud)
// DE/RE tied together and held LOW for receive-only mode

// ---- Board pin mapping notes ----
// Seeeduino XIAO (SAMD21): Serial1 TX=D6, RX=D7
// Arduino Zero / MKR family: Serial1 pins are fixed by the core

#define RS485_TX_PIN 6   // Informational only
#define RS485_RX_PIN 7   // Informational only
#define RE_DE_PIN 2      // Connect MAX485 RE+DE together and tie here

// Try different baud rates if 115200 doesn't work
#define RS485_BAUD 115200  // Common: 9600, 19200, 38400, 57600, 115200

#define FRAME_SYNC 0x55
#define MAX_FRAME_SIZE 64

// Frame buffer
uint8_t frameBuffer[MAX_FRAME_SIZE];
uint8_t frameIndex = 0;
bool inFrame = false;
unsigned long frameStartTime = 0;
unsigned long frameCount = 0;

void setup() {
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW);       // Receive-only mode

  Serial.begin(115200);               // USB CDC to computer
  while (!Serial && millis() < 3000); // Wait up to 3s for Serial Monitor

  Serial.println("LOGGER_READY");     // Signal for Python script
  Serial.flush();

  Serial1.begin(RS485_BAUD);          // RS-485 bus UART
}

void printFrame() {
  // Output format: FRAME,<timestamp_ms>,<hex_bytes>
  Serial.print("FRAME,");
  Serial.print(frameStartTime);
  Serial.print(",");

  for (uint8_t i = 0; i < frameIndex; i++) {
    if (frameBuffer[i] < 0x10) Serial.print("0");
    Serial.print(frameBuffer[i], HEX);
    if (i < frameIndex - 1) Serial.print(" ");
  }
  Serial.println();
  Serial.flush();

  frameCount++;
}

void loop() {
  unsigned long now = millis();

  // Read and buffer bytes into frames
  while (Serial1.available() > 0) {
    uint8_t b = Serial1.read();

    // Detect frame start (0x55 sync byte)
    if (b == FRAME_SYNC) {
      // If we were already in a frame, output the previous one
      if (inFrame && frameIndex > 0) {
        printFrame();
      }

      // Start new frame
      frameIndex = 0;
      frameBuffer[frameIndex++] = b;
      frameStartTime = now;
      inFrame = true;
    }
    else if (inFrame && frameIndex < MAX_FRAME_SIZE) {
      frameBuffer[frameIndex++] = b;

      // Check if frame is complete (have length field?)
      if (frameIndex >= 2) {
        uint8_t expectedLen = frameBuffer[1] + 2; // length + sync + length byte

        if (frameIndex >= expectedLen && expectedLen <= MAX_FRAME_SIZE) {
          printFrame();
          inFrame = false;
          frameIndex = 0;
        }
      }
    }
  }

  // Timeout for incomplete frames (100ms)
  if (inFrame && frameIndex > 0 && (now - frameStartTime > 100)) {
    // Output partial frame with ERROR marker
    Serial.print("ERROR,");
    Serial.print(frameStartTime);
    Serial.print(",TIMEOUT,");
    for (uint8_t i = 0; i < frameIndex; i++) {
      if (frameBuffer[i] < 0x10) Serial.print("0");
      Serial.print(frameBuffer[i], HEX);
      if (i < frameIndex - 1) Serial.print(" ");
    }
    Serial.println();
    Serial.flush();

    inFrame = false;
    frameIndex = 0;
  }

  // Handle commands from Serial Monitor
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "STATS") {
      Serial.print("STATUS,");
      Serial.print(now);
      Serial.print(",FRAMES=");
      Serial.print(frameCount);
      Serial.print(",UPTIME=");
      Serial.print(now / 1000);
      Serial.println("s");
      Serial.flush();
    }
    else if (cmd == "RESET") {
      frameCount = 0;
      Serial.println("STATUS,RESET");
      Serial.flush();
    }
  }
}
