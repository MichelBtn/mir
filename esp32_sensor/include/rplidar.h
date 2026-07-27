#include <Arduino.h>

// ── Protocole ─────────────────────────────────────────────────────────────────
const uint8_t SYNC_BYTE       = 0xA5;
const uint8_t SYNC_BYTE2      = 0x5A;
const uint8_t GET_INFO_BYTE   = 0x50;
const uint8_t GET_HEALTH_BYTE = 0x52;
const uint8_t STOP_BYTE       = 0x25;
const uint8_t RESET_BYTE      = 0x40;
const uint8_t SCAN_BYTE       = 0x20;
const uint8_t MOTOR_CTRL_BYTE = 0xA8;

const uint8_t  DESCRIPTOR_LEN    = 7;
const uint8_t  INFO_LEN          = 20;
const uint8_t  HEALTH_LEN        = 3;
const uint8_t  INFO_TYPE         = 4;
const uint8_t  HEALTH_TYPE       = 6;
const uint8_t  SCAN_TYPE         = 129;
const uint8_t  SCAN_SIZE         = 5;
const uint16_t DEFAULT_MOTOR_RPM = 600;
const uint16_t MAX_SCAN_POINTS   = 500;  // ~360 pts/tour + marge

// ── Structures ────────────────────────────────────────────────────────────────
struct LidarInfo {
    uint8_t model;
    uint8_t firmware_major;
    uint8_t firmware_minor;
    uint8_t hardware;
    char    serialnumber[33];
};

// ScanPoint compact pour transmission WiFi.
// angle    : dixièmes de degré  (0..3599)  → uint16_t
// distance : centimètres        (0..1200)  → uint16_t
// packed : 5 bytes/point au lieu de 12, soit 2500 bytes/scan à 10 Hz
struct __attribute__((packed)) ScanPoint {
    uint8_t  quality;    // 0..255
    uint16_t angle;      // dixièmes de degré  (0..3599)
    uint16_t distance;   // centimètres        (0 = invalide)
};

struct ScanData {
    ScanPoint points[MAX_SCAN_POINTS];
    uint16_t  count;
    uint32_t timestamp;
};

// ── Driver ────────────────────────────────────────────────────────────────────
class RPLidar {
public:
    explicit RPLidar(HardwareSerial& serial_port);

    bool begin(unsigned long baudrate = 460800,
               uint32_t timeout_ms   = 3000,
               int rx_pin = -1,
               int tx_pin = -1);
    void end();

    void startMotor(uint16_t rpm = DEFAULT_MOTOR_RPM);
    void stopMotor();
    bool getInfo(LidarInfo& info);
    bool getHealth(String& status, uint16_t& error_code);
    void stop();
    void reset();
    bool startScan();

    // Non-bloquant. Retourne true + remplit scan à chaque rotation complète.
    bool updateScan(ScanData& scan);

    bool isScanning()     const { return _scanning; }
    bool isMotorRunning() const { return _motor_running; }

private:
    HardwareSerial& _serial;
    uint32_t        _timeout;
    bool            _scanning;
    bool            _motor_running;

    // Accumulateur interne entre deux rotations
    ScanData        _accumulator;

    void _sendCmd(uint8_t cmd);
    void _sendPayloadCmd(uint8_t cmd, const uint8_t* payload, size_t len);
    bool _readDescriptor(uint32_t& data_len, bool& is_single, uint8_t& data_type);
    bool _readResponse(uint8_t* buffer, size_t size);
    void _flushInput();
};
