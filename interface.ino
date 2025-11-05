// SAMD21 + MAX485 DJI ESC Protocol Interface
// USB console: Serial (115200)
// RS-485 bus:  Serial1 (115200 8N1)
// DE/RE tied together and driven by RE_DE_PIN

// ---- Board pin mapping notes ----
// Seeeduino XIAO (SAMD21): Serial1 TX=D6, RX=D7
// Arduino Zero / MKR family: Serial1 pins are fixed by the core

#define RS485_TX_PIN 6   // XIAO TX (informational)
#define RS485_RX_PIN 7   // XIAO RX (informational)
#define RE_DE_PIN 2      // Connect MAX485 RE and DE together to this GPIO

// Frame constants
#define FRAME_SYNC 0x55
#define MAX_FRAME_SIZE 64
#define RX_TIMEOUT_MS 100

// Protocol state
uint8_t rxBuffer[MAX_FRAME_SIZE];
uint8_t rxIndex = 0;
unsigned long lastRxTime = 0;
bool inFrame = false;

void setup() {
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW);      // Receive mode by default

  Serial.begin(115200);               // USB CDC to computer
  while (!Serial && millis() < 2000); // Wait up to 2s for USB

  Serial1.begin(115200);              // RS-485 bus UART

  Serial.println("DJI ESC RS-485 Interface Ready");
  Serial.println("Commands: TX:HHHHH... (hex bytes), RX (receive mode)");
  Serial.println("Format: 55 1A 00 D0 A0 ...");
}

// Calculate simple 16-bit checksum (placeholder - replace with actual DJI algorithm)
uint16_t calcChecksum(uint8_t* data, uint8_t len) {
  uint16_t sum = 0;
  for (uint8_t i = 0; i < len; i++) {
    sum += data[i];
  }
  return sum;
}

// Send frame on RS-485 bus
void send485Frame(uint8_t* frame, uint8_t len) {
  digitalWrite(RE_DE_PIN, HIGH);      // Enable driver (TX)
  delayMicroseconds(50);              // Allow bus settle

  Serial1.write(frame, len);
  Serial1.flush();                    // Wait until bytes fully sent

  delayMicroseconds(50);              // Turnaround guard
  digitalWrite(RE_DE_PIN, LOW);       // Back to receive

  // Log to console
  Serial.print("[TX->485] ");
  for (uint8_t i = 0; i < len; i++) {
    if (frame[i] < 0x10) Serial.print("0");
    Serial.print(frame[i], HEX);
    Serial.print(" ");
  }
  Serial.println();
}

// Process received frame
void processRxFrame(uint8_t* frame, uint8_t len) {
  if (len < 8) return; // Too short

  Serial.print("[RX<-485] ");
  for (uint8_t i = 0; i < len; i++) {
    if (frame[i] < 0x10) Serial.print("0");
    Serial.print(frame[i], HEX);
    Serial.print(" ");
  }
  Serial.println();

  // Parse frame header
  uint8_t sync = frame[0];
  uint8_t length = frame[1];
  uint8_t flags = frame[2];
  uint16_t cmdId = frame[3] | (frame[4] << 8);
  uint16_t reserved = frame[5] | (frame[6] << 8);
  uint8_t sequence = frame[7];

  Serial.print("  CMD:0x");
  Serial.print(cmdId, HEX);
  Serial.print(" SEQ:");
  Serial.print(sequence);
  Serial.print(" LEN:");
  Serial.println(len);
}

// Parse hex string from Serial (e.g., "55 1A 00 D0 A0")
bool parseHexCommand(String cmd, uint8_t* buffer, uint8_t* outLen) {
  cmd.trim();
  uint8_t len = 0;
  int idx = 0;

  while (idx < cmd.length() && len < MAX_FRAME_SIZE) {
    // Skip whitespace
    while (idx < cmd.length() && cmd[idx] == ' ') idx++;
    if (idx >= cmd.length()) break;

    // Parse two hex digits
    if (idx + 1 < cmd.length()) {
      char hexByte[3] = {cmd[idx], cmd[idx+1], 0};
      buffer[len++] = strtol(hexByte, NULL, 16);
      idx += 2;
    } else {
      return false; // Odd number of hex digits
    }
  }

  *outLen = len;
  return len > 0;
}

void loop() {
  // Handle USB commands
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("TX:")) {
      // Format: TX:55 1A 00 D0 A0 ...
      String hexData = cmd.substring(3);
      uint8_t txBuffer[MAX_FRAME_SIZE];
      uint8_t txLen = 0;

      if (parseHexCommand(hexData, txBuffer, &txLen)) {
        send485Frame(txBuffer, txLen);
      } else {
        Serial.println("Error: Invalid hex format");
      }
    }
    else if (cmd == "RX") {
      Serial.println("Receive mode active (always listening)");
    }
    else if (cmd == "HELP") {
      Serial.println("Commands:");
      Serial.println("  TX:HHHHH...  - Send hex bytes on 485 bus");
      Serial.println("  RX           - Status (always receiving)");
      Serial.println("Example: TX:55 1A 00 D0 A0 00 00 01 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 00 00");
    }
    else {
      Serial.println("Unknown command. Type HELP");
    }
  }

  // Handle RS-485 reception with frame detection
  unsigned long now = millis();

  while (Serial1.available() > 0) {
    uint8_t b = Serial1.read();
    lastRxTime = now;

    // Detect frame start
    if (b == FRAME_SYNC) {
      rxIndex = 0;
      inFrame = true;
      rxBuffer[rxIndex++] = b;
    }
    else if (inFrame && rxIndex < MAX_FRAME_SIZE) {
      rxBuffer[rxIndex++] = b;

      // Check if we have length field and full frame
      if (rxIndex >= 2) {
        uint8_t expectedLen = rxBuffer[1] + 2; // length field + sync + length byte
        if (rxIndex >= expectedLen) {
          processRxFrame(rxBuffer, rxIndex);
          inFrame = false;
          rxIndex = 0;
        }
      }
    }
  }

  // Timeout on partial frame
  if (inFrame && (now - lastRxTime > RX_TIMEOUT_MS)) {
    Serial.print("[RX TIMEOUT] Partial: ");
    for (uint8_t i = 0; i < rxIndex; i++) {
      if (rxBuffer[i] < 0x10) Serial.print("0");
      Serial.print(rxBuffer[i], HEX);
      Serial.print(" ");
    }
    Serial.println();
    inFrame = false;
    rxIndex = 0;
  }
}
