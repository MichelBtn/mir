#include <Arduino.h>
#include "motor_bus.h"
#include "SCServo.h"

#define __DEBUG_MOTOR_BUS

void MotorBus::update_data() {
    //...
}

uint8_t* MotorBus::get_data_frame(uint16_t& len) {
    return nullptr;
}

namespace {

bool valid_uart_pins(int rx, int tx) {
    // ESP32 : GPIO 6-11 réservés au flash SPI, 34-39 input-only (pas de TX).
    auto usable = [](int p) { return p >= 0 && p <= 39 && (p < 6 || p > 11); };
    return usable(rx) && usable(tx) && tx < 34;
}

}

MotorBusInitStatus MotorBus::init(uint32_t baud, int rx_pin, int tx_pin) {
    _n_found = 0;
    if (!valid_uart_pins(rx_pin, tx_pin)) {
        _init_status = MotorBusInitStatus::UART_ERROR;
        return _init_status;
    }
    if (_initialized) {
        Serial2.end();
    }
    Serial2.begin(baud, SERIAL_8N1, rx_pin, tx_pin);
    sc.pSerial = &Serial2;
    // Timeout court pour la découverte : temps fil de ~12 octets + marge servo.
    // ≈ 10 ms à 1 Mbps, augmente automatiquement si baud faible.
    sc.IOTimeOut = max(10UL, (12UL * 10UL * 1000UL) / baud + 5UL);
    _initialized = true;

    // Ping broadcast : chaque servo répond une fois, en rafale déterministe.
    // Un bus présent répond toujours (même chemin retour qu'en unicast, pas
    // de niveau de retour désactivable côté STS). Sinon, le bus est muet.
    // Ping ne consomme que la première trame -> drainer les suivantes,
    // sinon l'inventaire est faux.
    int probe = sc.Ping(0xFE);
    if (probe >= 0 && probe <= 0xFD) {
        _found_ids[0] = (uint8_t)probe;
        _n_found = 1;
        drain_broadcast_responses();
    }
    sc.IOTimeOut = 100; // timeout nominal pour l'exploitation
    _init_status = (_n_found > 0) ? MotorBusInitStatus::OK : MotorBusInitStatus::NO_RESPONSE;
    return _init_status;
}

// Consomme les réponses encore en attente après un Ping broadcast réussi.
// Trame attendue : FF FF ID 02 ERR CHK, validée comme Ping (LEN + checksum).
void MotorBus::drain_broadcast_responses() {
    uint8_t win[6] = {0, 0, 0, 0, 0, 0};
    unsigned long deadline = millis() + 30;
    while ((long)(millis() - deadline) < 0) {
        int c = Serial2.read();
        if (c < 0) {
            continue;
        }
        memmove(win, win + 1, 5);
        win[5] = (uint8_t)c;
        deadline = millis() + 10; // prolonge tant que des octets arrivent
        if (win[0] == 0xFF && win[1] == 0xFF && win[3] == 0x02 && win[2] <= 0xFD &&
            win[5] == (uint8_t)~(win[2] + win[3] + win[4])) {
            bool known = false;
            for (uint8_t i = 0; i < _n_found; ++i) {
                if (_found_ids[i] == win[2]) {
                    known = true;
                    break;
                }
            }
            if (!known && _n_found < MAX_FOUND_IDS) {
                _found_ids[_n_found++] = win[2];
            }
            memset(win, 0, sizeof(win));
        }
    }
}

uint8_t MotorBus::get_found_count() const {
    return _n_found;
}

uint8_t MotorBus::get_found_ids(uint8_t* out, uint8_t max) const {
    if (out == nullptr || max == 0) {
        return 0;
    }
    uint8_t n = (_n_found < max) ? _n_found : max;
    memcpy(out, _found_ids, n);
    return n;
}

MotorBusResponseFrame MotorBus::make_response_frame(MotorBusErrors code) {
    return make_response_frame(code, nullptr, 0);
}

MotorBusResponseFrame MotorBus::make_response_frame(MotorBusErrors code, const uint8_t* payload, uint16_t payload_len) {
    constexpr uint16_t capacity = sizeof(_response_frame.response_buf);
    uint16_t total = 1 + payload_len;
    if (total > capacity) {
        total = capacity; // tronque, ne déborde jamais
    }
    _response_frame.response_buf[0] = static_cast<uint8_t>(code);
    if (payload != nullptr && total > 1) {
        memcpy(&_response_frame.response_buf[1], payload, total - 1);
    }
    _response_frame.len = total;
    return _response_frame;
}

MotorBusResponseFrame MotorBus::parse_and_run(
    const uint8_t* frame,
    uint16_t len
) {
    if (frame == nullptr || len < 1) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    if (static_cast<MotorBusCommands>(frame[0]) != MotorBusCommands::CMD_STATUS && _init_status != MotorBusInitStatus::OK)
        return make_response_frame(MotorBusErrors::NOT_CONNECTED);

    _response_frame.len = 0;

    switch (static_cast<MotorBusCommands>(frame[0])) {
        case MotorBusCommands::CMD_STATUS:
            return handle_status(frame, len);
        case MotorBusCommands::CMD_WRITE:
            return handle_write(frame, len);
        case MotorBusCommands::CMD_READ:
            return handle_read(frame, len);
        case MotorBusCommands::CMD_SYNC_WRITE:
            return handle_sync_write(frame, len);
        case MotorBusCommands::CMD_SYNC_READ:
            return handle_sync_read(frame, len);
        default:
            #ifdef __DEBUG_MOTOR_BUS
            Serial.print("MotorBus: unknown command 0x");
            Serial.println(frame[0], HEX);
            #endif
            return make_response_frame(MotorBusErrors::UNKNOWN_CMD);
    }
}

MotorBusResponseFrame MotorBus::handle_status(const uint8_t* frame, uint16_t len) {
    // STATUS : [cmd]
    if (len != 1) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }

    uint8_t data[1];
    data[0] = (uint8_t)_init_status;    
    return make_response_frame(MotorBusErrors::OK, data, 1);    
}

MotorBusResponseFrame MotorBus::handle_write(const uint8_t* frame, uint16_t len) {
    // WRITE : [cmd, id, addr, d0(, d1)]
    if (len < 4) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }

    uint8_t id   = frame[1];
    uint8_t addr = frame[2];

    const uint8_t* data = &frame[3];
    uint16_t data_len = len - 3;
    
    #ifdef __DEBUG_MOTOR_BUS
    Serial.print("WRITE: ID=");
    Serial.print(id, HEX);
    Serial.print(" ADDR=");
    Serial.print(addr, HEX);
    Serial.print(" DATA=");
    for (uint16_t i = 0; i < data_len; ++i) {
        if (data[i] < 0x10)
            Serial.print('0');
        Serial.print(data[i], HEX);
        Serial.print(' ');
    }
    Serial.println();
    #endif

    int result;

    if (data_len == 1) {
        result = sc.writeByte(id, addr, data[0]);
    }
    else if (data_len == 2) {
        result = sc.writeWord(
            id,
            addr,
            data[0] | ((uint16_t)data[1] << 8)
        );
    }
    else {
        #ifdef __DEBUG_MOTOR_BUS
        Serial.println("MotorBus: unsupported WRITE length");
        #endif
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }
    #ifdef __DEBUG_MOTOR_BUS
    Serial.print("SCServo result = ");
    Serial.println(result);
    #endif

    // writeByte/writeWord : 1 = ACK reçu (ou broadcast, sans ACK), 0 = échec.
    if (result == 1)
        return make_response_frame(MotorBusErrors::OK);
    return make_response_frame(MotorBusErrors::STS_NACK);
}

MotorBusResponseFrame MotorBus::handle_read(const uint8_t* frame, uint16_t len) {
    // READ : [cmd, id, addr, count] -> [status, d0, ...]
    if (len != 4) {
        Serial.println("BAD_FRAME");
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }

    uint8_t id    = frame[1];
    uint8_t addr  = frame[2];
    uint8_t count = frame[3];

    if (id == 0xFE) {
        #ifdef __DEBUG_MOTOR_BUS
        Serial.println("BAD_ARG");
        #endif
        return make_response_frame(MotorBusErrors::BAD_ARG);
    }
    if (count == 0) {
        #ifdef __DEBUG_MOTOR_BUS
        Serial.println("BAD_LEN");
        #endif        
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }

    #ifdef __DEBUG_MOTOR_BUS
    Serial.print("READ: ID=");
    Serial.print(id, HEX);
    Serial.print(" ADDR=");
    Serial.print(addr, HEX);
    Serial.print(" COUNT=");
    Serial.println(count);
    #endif

    uint8_t data[255]; // count <= 255 = capacité réponse - status
    int result = sc.Read(id, addr, data, count);

    #ifdef __DEBUG_MOTOR_BUS
    Serial.print("SCServo result = ");
    Serial.println(result);
    #endif

    // Read : nombre d'octets lus, 0 = échec (timeout, checksum).
    if (result != count)
        return make_response_frame(MotorBusErrors::STS_NACK);
    return make_response_frame(MotorBusErrors::OK, data, count);
}

MotorBusResponseFrame MotorBus::handle_sync_write(const uint8_t* frame, uint16_t len) {
    // SYNC_WRITE : [cmd, nid, id.., nreg, (reg, len, data_m0.., gap_L, gap_H)..]
    //   -> [status]. Par registre : nid blocs de len octets (bloc i = valeur
    //   du moteur i), soit nreg appels SCS::syncWrite. len est commun à tous
    //   les moteurs d'un même registre (contrainte SCS). gap = attente en µs
    //   (uint16 little-endian) après l'écriture, pour laisser le temps au
    //   servo de prendre en compte le registre avant le suivant (ex. vitesse
    //   reg 46 puis consigne reg 42). Ignorée après le dernier registre pour
    //   ne pas retarder la réponse. Bloque la boucle pendant l'attente.
    // syncWrite est un broadcast sans réponse : pas de STS_NACK possible,
    // le retour est OK dès que la trame est valide et émise.
    if (frame == nullptr || len < 5) { // garde rapide, contrôles stricts dessous
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    uint16_t off = 1;
    uint8_t nid = frame[off++];
    if (nid == 0) {
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }
    if (off + nid > len) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    for (uint8_t i = 0; i < nid; ++i) {
        if (frame[off + i] > 0xFD) { // 0xFE = broadcast, invalide comme cible
            return make_response_frame(MotorBusErrors::BAD_ARG);
        }
    }
    // syncWrite ne modifie ni les IDs ni les données (lecture seule vérifiée
    // dans SCS.cpp) : zéro-copie, on pointe dans la trame reçue. Le layout
    // nid blocs de len octets correspond exactement au nDat attendu.
    uint8_t* ids = const_cast<uint8_t*>(&frame[off]);
    off += nid;
    if (off >= len) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    uint8_t nreg = frame[off++];
    if (nreg == 0) {
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }
    for (uint8_t r = 0; r < nreg; ++r) {
        if (off + 2 > len) {
            return make_response_frame(MotorBusErrors::BAD_FRAME);
        }
        uint8_t reg = frame[off++];
        uint8_t slen = frame[off++];
        if (slen == 0) {
            return make_response_frame(MotorBusErrors::BAD_LEN);
        }
        uint16_t need = (uint16_t)nid * slen;
        if (off + need + 2 > len) { // +2 : gap_L, gap_H
            return make_response_frame(MotorBusErrors::BAD_FRAME);
        }
        // Limite protocole SCS : mesLen = (slen+1)*nid+4 tient sur un octet.
        if ((uint16_t)(slen + 1) * nid + 4 > 255) {
            return make_response_frame(MotorBusErrors::BAD_LEN);
        }
        uint8_t* data = const_cast<uint8_t*>(&frame[off]);
        off += need;
        uint16_t gap_us = (uint16_t)frame[off] | ((uint16_t)frame[off + 1] << 8);
        off += 2;
        #ifdef __DEBUG_MOTOR_BUS
        Serial.print("SYNC_WRITE: NID=");
        Serial.print(nid);
        Serial.print(" REG=");
        Serial.print(reg, HEX);
        Serial.print(" LEN=");
        Serial.print(slen);
        Serial.print(" GAP_US=");
        Serial.println(gap_us);
        #endif
        sc.syncWrite(ids, nid, reg, data, slen);
        if (gap_us != 0 && r + 1 < nreg) {
            delayMicroseconds(gap_us);
        }
    }
    if (off != len) { // octets traînants : trame mal formée
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    return make_response_frame(MotorBusErrors::OK);
}

MotorBusResponseFrame MotorBus::handle_sync_read(const uint8_t* frame, uint16_t len) {
    // SYNC_READ : [cmd, nid, id.., addr, count] -> [status, data_m0.., data_m1..]
    //   count octets contigus depuis addr sur les nid moteurs, données groupées
    //   par moteur dans l'ordre des IDs. count commun (contrainte SCS syncRead).
    //   Un seul syncReadPacketTx puis un syncReadPacketRx par moteur.
    if (frame == nullptr || len < 5) { // cmd + nid + 1 id + addr + count min
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    uint16_t off = 1;
    uint8_t nid = frame[off++];
    if (nid == 0) {
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }
    if (off + nid > len) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    for (uint8_t i = 0; i < nid; ++i) {
        if (frame[off + i] > 0xFD) { // 0xFE = broadcast, invalide comme cible
            return make_response_frame(MotorBusErrors::BAD_ARG);
        }
    }
    // syncReadPacketTx ne modifie pas le tableau d'IDs (lecture seule).
    uint8_t* ids = const_cast<uint8_t*>(&frame[off]);
    off += nid;
    if (off + 2 > len) {
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    uint8_t addr  = frame[off++];
    uint8_t count = frame[off++];
    if (count == 0) {
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }
    if (off != len) { // octets traînants : trame mal formée
        return make_response_frame(MotorBusErrors::BAD_FRAME);
    }
    // Capacité réponse : 1 (status) + nid*count <= sizeof(response_buf).
    if ((uint16_t)nid * count > 255) {
        return make_response_frame(MotorBusErrors::BAD_LEN);
    }

    #ifdef __DEBUG_MOTOR_BUS
    Serial.print("SYNC_READ: NID=");
    Serial.print(nid);
    Serial.print(" ADDR=");
    Serial.print(addr, HEX);
    Serial.print(" COUNT=");
    Serial.println(count);
    #endif

    // Purge le buffer RX : syncReadPacketTx, contrairement à Read/syncWrite,
    // n'appelle pas rFlushSCS ; des checksums résiduels traîneraient d'une
    // transaction précédente.
    while (Serial2.available()) {
        Serial2.read();
    }

    sc.syncReadPacketTx(ids, nid, addr, count);
    uint8_t data[255];
    for (uint8_t i = 0; i < nid; ++i) {
        // Réponse par moteur, dans l'ordre des IDs ; 0 = échec (timeout,
        // en-tête). Erreur servo (Error) non traitée, comme Read.
        if (sc.syncReadPacketRx(ids[i], &data[i * count]) != count) {
            #ifdef __DEBUG_MOTOR_BUS
            Serial.print("SYNC_READ: no/failed response for ID=");
            Serial.println(ids[i]);
            #endif
            return make_response_frame(MotorBusErrors::STS_NACK);
        }
        // La lib SCS ne consomme pas l'octet de checksum en fin de réponse
        // (SCS.cpp:325, bBuf[4] déclaré mais 3 octets lus). On le jette, sinon
        // un checksum 0xFF serait pris pour l'en-tête FF FF de la réponse
        // suivante et désynchroniserait la trame.
        Serial2.read();
    }
    return make_response_frame(MotorBusErrors::OK, data, (uint16_t)nid * count);
}