#ifndef __MOTOR_BUS__H
#define __MOTOR_BUS__H

#include "SCServo.h"

struct MotorBusResponseFrame {
    uint8_t response_buf[256];    
    uint16_t len;
};

// Protocole (binaire, longueur uint16 big-endian côté TCP, voir main.cpp) :
//   STATUS : [0x01] -> [status, bus_init_status]   
//   WRITE : [0x02, id, addr, d0(, d1)] -> [status]
//   READ  : [0x03, id, addr, count]    -> [status, d0, ...]
// Données en little-endian (poids faible d'abord), comme le bus SCS.
enum class MotorBusCommands : uint8_t {
    CMD_STATUS = 0x01,
    CMD_WRITE = 0x02,
    CMD_READ = 0x03,
};

enum class MotorBusErrors : uint8_t {
    OK =            0x00,
    NOT_CONNECTED = 0x01,
    UNKNOWN_CMD =   0x02,
    BAD_LEN =       0x03,
    BAD_FRAME =     0x04,
    STS_NACK =      0x05,
    BAD_ARG =       0x06  // argument invalide (ex. READ en broadcast)
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
    MotorBusResponseFrame handle_write(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_read(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_status(const uint8_t* frame, uint16_t len);
    MotorBusInitStatus _init_status = MotorBusInitStatus::NO_RESPONSE;
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
