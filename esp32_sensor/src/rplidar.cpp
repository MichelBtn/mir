#include "rplidar.h"

RPLidar::RPLidar(HardwareSerial& serial_port) 
    : _serial(serial_port), _timeout(3000), _scanning(false), _motor_running(false) {
    _accumulator.count = 0;
}

bool RPLidar::begin(unsigned long baudrate, uint32_t timeout_ms, int rx_pin, int tx_pin) {
    _timeout = timeout_ms;
    if (rx_pin >= 0 && tx_pin >= 0)
        _serial.begin(baudrate, SERIAL_8N1, rx_pin, tx_pin);
    else
        _serial.begin(baudrate, SERIAL_8N1);

    // Attendre et vider la bannière de boot ("RP S2 LIDAR System.\r\n")
    uint32_t deadline = millis() + 3000;
    while (millis() < deadline) {
        delay(100);
        if (_serial.available() == 0) {
            delay(200);
            if (_serial.available() == 0) break;
        }
    }
    _flushInput();
    return true;
}

void RPLidar::end() {
    _serial.end();
}

void RPLidar::_sendCmd(uint8_t cmd) {
    uint8_t req[2] = { SYNC_BYTE, cmd };
    _serial.write(req, 2);
}

void RPLidar::_sendPayloadCmd(uint8_t cmd, const uint8_t* payload, size_t len) {
    // Taille fixe — pas de VLA en C++
    static constexpr size_t MAX_PAYLOAD = 16;
    uint8_t buf[3 + MAX_PAYLOAD + 1];

    buf[0] = SYNC_BYTE;
    buf[1] = cmd;
    buf[2] = (uint8_t)len;
    for (size_t i = 0; i < len; i++) buf[3 + i] = payload[i];

    uint8_t checksum = 0;
    for (size_t i = 0; i < 3 + len; i++) checksum ^= buf[i];
    buf[3 + len] = checksum;

    _serial.write(buf, 3 + len + 1);
}

void RPLidar::_flushInput() {
    while (_serial.available() > 0) _serial.read();
}

bool RPLidar::_readResponse(uint8_t* buffer, size_t size) {
    uint32_t start = millis();
    size_t   index = 0;
    while (index < size) {
        if (millis() - start > _timeout) return false;
        if (_serial.available() > 0) buffer[index++] = _serial.read();
        yield();
    }
    return true;
}

bool RPLidar::_readDescriptor(uint32_t& data_len, bool& is_single, uint8_t& data_type) {
    uint8_t desc[DESCRIPTOR_LEN];
    if (!_readResponse(desc, DESCRIPTOR_LEN)) return false;
    if (desc[0] != SYNC_BYTE || desc[1] != SYNC_BYTE2) return false;

    data_len  = desc[2] | (desc[3] << 8) | (desc[4] << 16) | ((desc[5] & 0x3F) << 24);
    is_single = ((desc[5] >> 6) & 0x03) == 0x00;
    data_type = desc[6];
    return true;
}

void RPLidar::startMotor(uint16_t rpm) {
    uint8_t payload[2] = { (uint8_t)(rpm & 0xFF), (uint8_t)(rpm >> 8) };
    _sendPayloadCmd(MOTOR_CTRL_BYTE, payload, 2);
    _motor_running = true;
    delay(1000);
}

void RPLidar::stopMotor() {
    uint8_t payload[2] = {0, 0};
    _sendPayloadCmd(MOTOR_CTRL_BYTE, payload, 2);
    _motor_running = false;
}

bool RPLidar::getInfo(LidarInfo& info) {
    _flushInput();
    _sendCmd(GET_INFO_BYTE);

    uint32_t dsize; bool is_single; uint8_t dtype;
    if (!_readDescriptor(dsize, is_single, dtype)) return false;
    if (dsize != INFO_LEN || !is_single || dtype != INFO_TYPE) return false;

    uint8_t raw[INFO_LEN];
    if (!_readResponse(raw, INFO_LEN)) return false;

    info.model          = raw[0];
    info.firmware_minor = raw[1];
    info.firmware_major = raw[2];
    info.hardware       = raw[3];
    for (int i = 0; i < 16; i++) sprintf(&info.serialnumber[i * 2], "%02X", raw[4 + i]);
    info.serialnumber[32] = '\0';
    return true;
}

bool RPLidar::getHealth(String& status, uint16_t& error_code) {
    _flushInput();
    _sendCmd(GET_HEALTH_BYTE);

    uint32_t dsize; bool is_single; uint8_t dtype;
    if (!_readDescriptor(dsize, is_single, dtype)) return false;
    if (dsize != HEALTH_LEN || !is_single || dtype != HEALTH_TYPE) return false;

    uint8_t raw[HEALTH_LEN];
    if (!_readResponse(raw, HEALTH_LEN)) return false;

    uint8_t s = raw[0];
    status     = (s == 0) ? "Good" : (s == 1) ? "Warning" : "Error";
    error_code = raw[1] | (raw[2] << 8);
    return true;
}

void RPLidar::stop() {
    _sendCmd(STOP_BYTE);
    delay(50);
    _flushInput();
    _scanning = false;
}

void RPLidar::reset() {
    _sendCmd(RESET_BYTE);
    delay(2000);
    _flushInput();
}

bool RPLidar::startScan() {
    String status; uint16_t error_code;
    if (!getHealth(status, error_code)) return false;
    if (status == "Error") {
        reset();
        if (!getHealth(status, error_code) || status == "Error") return false;
    }

    _sendCmd(SCAN_BYTE);

    uint32_t dsize; bool is_single; uint8_t dtype;
    if (!_readDescriptor(dsize, is_single, dtype)) return false;
    if (dsize != SCAN_SIZE || is_single || dtype != SCAN_TYPE) return false;

    // Petite pause pour stabiliser le moteur — mais PAS de flush :
    // les packets de scan arrivent dès le descriptor et les jeter
    // désaligne le stream.
    delay(100);

    _scanning = true;
    return true;
}

bool RPLidar::updateScan(ScanData& scan) {
    if (!_motor_running || !_scanning) return false;

    // Drainer tout le buffer disponible en une passe
    while (_serial.available() >= SCAN_SIZE) {

        uint8_t b0 = _serial.peek();
        uint8_t s  = b0 & 0x01;
        uint8_t s_ = (b0 >> 1) & 0x01;

        if (s == s_) {
            _serial.read();  // byte invalide, resync
            continue;
        }

        uint8_t raw[SCAN_SIZE];
        _serial.readBytes(raw, SCAN_SIZE);

        if ((raw[1] & 0x01) != 1)
            continue;  // check bit invalide, on ignore ce packet

        bool is_new_scan = (raw[0] & 0x01) == 1;
        ScanPoint point;
        point.quality  = raw[0] >> 2;
        // Angle en dixièmes de degré (résolution capteur : 0.72°)
        float angle_deg   = ((raw[1] >> 1) + (raw[2] << 7)) / 64.0f;
        point.angle       = (uint16_t)(angle_deg * 10.0f + 0.5f) % 3600;
        // Distance en cm (capteur donne des mm/4, précision ±30 mm)
        float dist_mm     = (raw[3] + (raw[4] << 8)) / 4.0f;
        uint16_t dist_cm  = (uint16_t)(dist_mm / 10.0f + 0.5f);
        point.distance    = (dist_cm > 1200) ? 1200 : dist_cm;

        if (is_new_scan && _accumulator.count > 0) {
            // Rotation complète — livrer l'accumulateur et repartir
            scan = _accumulator;
            _accumulator.count = 0;
            if (point.distance > 0.f && _accumulator.count < MAX_SCAN_POINTS)
                _accumulator.points[_accumulator.count++] = point;
            return true;
        }

        if (point.distance > 0.f && _accumulator.count < MAX_SCAN_POINTS)
            _accumulator.points[_accumulator.count++] = point;
    }

    return false;
}
