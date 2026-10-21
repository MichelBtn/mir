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
//   SYNC_WRITE : [0x04, nid, id.., nreg, (reg, len, data_m0.., gap_L, gap_H)..] -> [status]
//     Valeur propre à chaque moteur : par registre, nid blocs de len octets
//     (moteur i -> bloc i), soit nreg appels syncWrite. len commun par
//     registre (contrainte SCS). gap = attente µs (uint16 little-endian)
//     après l'écriture du registre, ignorée pour le dernier (réponse immédiate).
//   SYNC_READ : [0x05, nid, id.., addr, count] -> [status, data_m0.., data_m1..]
//     Lit count octets contigus à partir de addr sur les nid moteurs ; les
//     données reviennent groupées par moteur, dans l'ordre des IDs. count est
//     commun à tous les moteurs (contrainte SCS syncRead).
// Données en little-endian (poids faible d'abord), comme le bus SCS.
enum class MotorBusCommands : uint8_t {
    CMD_STATUS = 0x01,
    CMD_WRITE = 0x02,
    CMD_READ = 0x03,
    CMD_SYNC_WRITE = 0x04,
    CMD_SYNC_READ = 0x05,
    CMD_RESCAN_BUS = 0x10,
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
public:
    static constexpr uint8_t MAX_FOUND_IDS = 32;
private:
    // ─── Flux de télémétrie (update_data / get_data_frame) ──────────────────
    // Trame : [version u8][n u8][counter u16 LE][stride u8]
    //         puis n × [id u8][pos i16][vel i16][load i16][volt u8][temp u8][current i16]
    // Little-endian, valeurs brutes SCS (aucune normalisation) ; l'ordre des
    // moteurs est celui de _found_ids. Deux syncRead contigus, car SCS ne lit
    // qu'un seul bloc (addr, len) à la fois :
    //   A = 0x38..0x3F (Position, Velocity, Load, Voltage, Temperature)
    //   B = 0x45..0x46 (Current)
    static constexpr uint8_t STREAM_VERSION = 1;
    static constexpr uint8_t STREAM_BLOCK_A_ADDR = 0x38;
    static constexpr uint8_t STREAM_BLOCK_A_SIZE = 8;
    static constexpr uint8_t STREAM_BLOCK_B_ADDR = 0x45;
    static constexpr uint8_t STREAM_BLOCK_B_SIZE = 2;
    static constexpr uint8_t STREAM_DATA_SIZE = STREAM_BLOCK_A_SIZE + STREAM_BLOCK_B_SIZE;
    static constexpr uint8_t STREAM_RECORD_SIZE = 1 + STREAM_DATA_SIZE; // id + données
    static constexpr uint8_t STREAM_HEADER_SIZE = 5;
    static constexpr uint16_t STREAM_MAX_FRAME_SIZE =
        STREAM_HEADER_SIZE + MAX_FOUND_IDS * STREAM_RECORD_SIZE;
    // Timeout court : le streaming ne doit pas bloquer la boucle principale.
    static constexpr uint16_t STREAM_IO_TIMEOUT_MS = 10;

    SMS_STS sc;
    MotorBusResponseFrame _response_frame;
    bool _initialized = false;
    uint8_t _found_ids[MAX_FOUND_IDS];
    uint8_t _n_found = 0;
    uint32_t _baud = 0;
    uint8_t _data_frame[STREAM_MAX_FRAME_SIZE];
    uint16_t _data_frame_len = 0;
    uint16_t _data_counter = 0;
    // Lit un bloc contigu (addr, count) sur nid moteurs ; données groupées par
    // moteur dans l'ordre des ids. Gère la purge RX et le checksum final.
    bool sync_read_block(uint8_t* ids, uint8_t nid, uint8_t addr, uint8_t count, uint8_t* out);
    MotorBusResponseFrame make_response_frame(MotorBusErrors code);
    MotorBusResponseFrame make_response_frame(MotorBusErrors code, const uint8_t* payload, uint16_t payload_len);
    MotorBusResponseFrame handle_write(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_read(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_status(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_sync_write(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_sync_read(const uint8_t* frame, uint16_t len);
    MotorBusResponseFrame handle_rescan_bus(const uint8_t* frame, uint16_t len);
    MotorBusInitStatus scan_bus();
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
