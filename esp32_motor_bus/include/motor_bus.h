class MotorBus {
public:
    void update_data();
    uint8_t* get_data_frame(uint16_t& len);
    bool init();
};

