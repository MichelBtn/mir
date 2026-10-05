#ifndef __MOTOR_BUS__H
#define __MOTOR_BUS__H

#include "SCServo.h"

struct MotorBusResponseFrame {
    uint8_t response_buf[256];    
    uint16_t len;
};

enum class MotorBusCommands : uint8_t {
    CMD_WRITE = 0x02,
};

enum class MotorBusErrors : uint8_t {
    OK =          0x00,
    UNKNOWN_CMD = 0x01,
    BAD_LEN =     0x02,
    BAD_FRAME =   0x03,
    STS_NACK =    0x04
};

enum class MotorBusInitStatus : uint8_t {
    OK = 0,          // un servo a répondu : TX + RX + baud prouvés
    UART_ERROR = 1,  // pins invalides (erreur de config détectable avant begin)
    NO_RESPONSE = 2, // silence après timeout : cause ambiguë (voir init)
};

class MotorBus {
    SMS_STS sc;
    MotorBusResponseFrame _response_frame;
    bool _initialized = false;
    static constexpr uint8_t MAX_FOUND_IDS = 32;
    uint8_t _found_ids[MAX_FOUND_IDS];
    uint8_t _n_found = 0;
    void drain_broadcast_responses();
    MotorBusResponseFrame make_response_frame(MotorBusErrors code);
    MotorBusResponseFrame make_response_frame(MotorBusErrors code, const uint8_t* payload, uint16_t payload_len);
public:
    void update_data();
    uint8_t* get_data_frame(uint16_t& len);
    // Découverte sans ID connu : Ping broadcast + collecte.
    // OK = au moins un servo a répondu (voir get_found_ids).
    // NO_RESPONSE = silence total (bus hors tension, câblage, baud, aucun servo).
    MotorBusInitStatus init(uint32_t baud = 1000000, int rx_pin = 16, int tx_pin = 17);
    uint8_t get_found_count() const;
    uint8_t get_found_ids(uint8_t* out, uint8_t max) const;
    MotorBusResponseFrame parse_and_run(const uint8_t* frame,  uint16_t len);
};


#endif
