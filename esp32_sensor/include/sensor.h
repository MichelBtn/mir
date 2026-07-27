#ifndef __sensor__h__
#define __sensor__h__

#include <Arduino.h>

class Sensor {
public:
    static constexpr uint8_t MAGIC_0 = 0xA5;
    static constexpr uint8_t MAGIC_1 = 0x5A;

private:
    //uint16_t crc16(const uint8_t* data, size_t len);

protected:
    uint64_t timestamp;
    virtual bool _add_frame_data(int& pos) = 0;
    virtual void _update_data() = 0;
    uint8_t* _buffer;
    char _id[32];
    uint32_t _sequence = 0;

public:
    Sensor(const char* id, size_t data_buffer_size);
    void     update_data();
    uint8_t* get_data_frame(uint16_t& len);
    virtual bool        init()            = 0;
    virtual const char* read_data()       = 0;
    virtual const char* get_data_schema() = 0;
};

#endif
