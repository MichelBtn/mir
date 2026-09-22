#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "ble_provisioning.h"
#include "command.h"
#include "lwip/sockets.h"
#include "sensor_simulation.h"
#include "sensor_wheather.h"
#include "sensor_lidar.h"

Preferences prefs;
Sensor* _sensor;
char sensor_type[20];
char sensor_id[32];
char ap1_ssid[32];
char ap1_pwd[32];
char ap1_ip[20];
char ap2_ssid[32];
char ap2_pwd[32];
char ap2_ip[20];
int32_t wifi_timeout = 10;
int16_t loop_period = 50;

WiFiClient client;
const uint16_t TCP_PORT = 5000;
IPAddress current_ip;
WiFiServer tcpServer(TCP_PORT);

const uint16_t TCP_DATA_PORT = 5001;
WiFiServer    tcpDataServer(TCP_DATA_PORT);
WiFiClient    tcp_data_client;

String serial_buffer;
String tcp_buffer;
Command command;

WiFiUDP discovery_udp;
const uint16_t DISCOVERY_LISTEN_PORT = 5679;
const uint16_t DISCOVERY_RESPONSE_PORT = 5678;

char short_response[256];
char arg_short_response[256];
bool wifi_connected;

BleProvisioning bleProv;

enum class CommandSource : uint8_t {
  SerialOnly,
  Tcp,
};

void set_str_value(char* param, size_t param_size, const String& new_value) {
  if (new_value.isEmpty())
    return;
  strncpy(param, new_value.c_str(), param_size - 1);
  param[param_size - 1] = '\0';
}

void send_response(Stream& stream, const char* cmd, const char* response) {
  snprintf(short_response, sizeof(short_response), "#%s %s\n", cmd, response);
  stream.print(short_response);
}

void load_configuration() {
  prefs.begin("sensor_cfg", false);
  set_str_value(sensor_type, sizeof(sensor_type), prefs.getString("sensor_type", "simulation"));
  set_str_value(sensor_id, sizeof(sensor_id), prefs.getString("sensor_id", "esp_0"));
  set_str_value(ap1_ssid, sizeof(ap1_ssid), prefs.getString("ap1_ssid", ""));
  set_str_value(ap1_pwd, sizeof(ap1_pwd), prefs.getString("ap1_pwd", ""));
  set_str_value(ap1_ip, sizeof(ap1_ip), prefs.getString("ap1_ip", "auto"));
  set_str_value(ap2_ssid, sizeof(ap2_ssid), prefs.getString("ap2_ssid", ""));
  set_str_value(ap2_pwd, sizeof(ap2_pwd), prefs.getString("ap2_pwd", ""));
  set_str_value(ap2_ip, sizeof(ap2_ip), prefs.getString("ap2_ip", "auto"));
  wifi_timeout = prefs.getInt("wifi_timeout", 5);
  if(wifi_timeout < 2) {
    Serial.print("wifi_timeout invalide : ");
    Serial.print(wifi_timeout);
    Serial.println(". utiliser la valeur par défaut (5s).");
    wifi_timeout = 5;
  }
  loop_period = prefs.getInt("loop_period", 25);
  if(loop_period < 10) {
    Serial.print("loop_period invalide : ");
    Serial.print(loop_period);
    Serial.println(". utiliser la valeur par défaut (25ms).");
    loop_period = 25;
  }
  prefs.end();

  if (strcmp(sensor_type, SensorLidar::sensor_type()) == 0)
    _sensor = new SensorLidar(sensor_id);
  else if (strcmp(sensor_type, SensorWheather::sensor_type()) == 0)
    _sensor = new SensorWheather(sensor_id);
  else {
    set_str_value(sensor_type, sizeof(sensor_type), SensorSimulation::sensor_type());
    _sensor = new SensorSimulation(sensor_id);
  }
}

void print_configuration() {
  Serial.print("sensor_type : ");
  Serial.println(sensor_type);
  Serial.print("sensor_id : ");
  Serial.println(sensor_id);
  Serial.print("ap1_ssid : ");
  Serial.println(ap1_ssid);
  Serial.print("ap1_pwd : ");
  Serial.println(ap1_pwd);
  Serial.print("ap1_ip : ");
  Serial.println(ap1_ip);
  Serial.print("ap2_ssid : ");
  Serial.println(ap2_ssid);
  Serial.print("ap2_pwd : ");
  Serial.println(ap2_pwd);
  Serial.print("ap2_ip : ");
  Serial.println(ap2_ip);
  Serial.print("wifi_timeout : ");
  Serial.println(wifi_timeout);
}

bool connect_to_ap(const char* ssid, const char* pwd, const char* ip_addr) {
  // Coexistence WiFi + BLE : le modem sleep DOIT rester activé tant que le
  // BLE est actif, sinon le driver WiFi abort ("Should enable WiFi modem
  // sleep when both WiFi and Bluetooth are enabled"). On le réactive en
  // mode NONE une fois le BLE arrêté (voir BleProvisioning::stop()).
  WiFi.setSleep(bleProv.isActive() ? WIFI_PS_MIN_MODEM : WIFI_PS_NONE);
  WiFi.mode(WIFI_STA);
  if (strcmp(ip_addr, "auto") != 0) {
    IPAddress ip;
    ip.fromString(ip_addr);
    WiFi.config(ip, IPAddress(0, 0, 0, 0), IPAddress(255, 255, 255, 0));
  }
  Serial.print("connecting to AP : ");
  Serial.print(ssid);
  WiFi.begin(ssid, pwd);
  bool timed_out = false;
  int count = 0;
  while (WiFi.status() != WL_CONNECTED && !timed_out) {
    Serial.print(".");
    delay(500);
    if (++count >= wifi_timeout * 2)
      timed_out = true;
  }
  if (timed_out) {
    Serial.println(" failed.");
  } else {
    Serial.println(" succeeded.");
  }
  return !timed_out;
}

void test() {
  _sensor->update_data();
  Serial.println(_sensor->read_data());
}

void save_configuration() {
  prefs.begin("sensor_cfg", false);
  prefs.putString("sensor_type", sensor_type);
  prefs.putString("sensor_id", sensor_id);
  prefs.putString("ap1_ssid", ap1_ssid);
  prefs.putString("ap1_pwd", ap1_pwd);
  prefs.putString("ap1_ip", ap1_ip);
  prefs.putString("ap2_ssid", ap2_ssid);
  prefs.putString("ap2_pwd", ap2_pwd);
  prefs.putString("ap2_ip", ap2_ip);
  prefs.putInt("wifi_timeout", wifi_timeout);
  prefs.putInt("loop_period", loop_period);
  prefs.end();
}

void set_configuration(Stream& stream, const Command& command) {
  String arg_value;
  if((arg_value = command.getArgValue("sensor_type")).length() > 0)  {
    set_str_value(sensor_type, sizeof(sensor_type), arg_value);
  }
  if((arg_value = command.getArgValue("sensor_id")).length() > 0) {
    set_str_value(sensor_id, sizeof(sensor_id), arg_value);
  }
  if((arg_value = command.getArgValue("ap1_ip")).length() > 0) {
    set_str_value(ap1_ip, sizeof(ap1_ip), arg_value);
  }
  if((arg_value = command.getArgValue("ap2_ip")).length() > 0) {
    set_str_value(ap2_ip, sizeof(ap2_ip), arg_value);
  }
  if((arg_value = command.getArgValue("wifi_timeout")).length() > 0) {
    wifi_timeout = arg_value.toInt();
  }
  if((arg_value = command.getArgValue("loop_period")).length() > 0) {
    int val = arg_value.toInt();
    if(val > 10 && val < 1000)
      loop_period = val;
  }
  save_configuration();
  send_response(stream, "set_configuration", "status=success");
}

void set_ap_configuration(Stream& stream, const Command& command) {
  String arg_value;
  if((arg_value = command.getArgValue("ap1_ssid")).length() > 0)  {
    set_str_value(ap1_ssid, sizeof(ap1_ssid), arg_value);
  }
  if((arg_value = command.getArgValue("ap1_pwd")).length() > 0) {
    set_str_value(ap1_pwd, sizeof(ap1_pwd), arg_value);
  }
  if((arg_value = command.getArgValue("ap2_ssid")).length() > 0) {
    set_str_value(ap2_ssid, sizeof(ap2_ssid), arg_value);
  }
  if((arg_value = command.getArgValue("ap2_pwd")).length() > 0) {
    set_str_value(ap2_pwd, sizeof(ap2_pwd), arg_value);
  }
  save_configuration();
  send_response(stream, "set_ap_configuration", "status=success");
}

// Callback du provisioning BLE : stocke les identifiants reçus comme
// set_ap_configuration (paramètres ap1_ssid / ap1_pwd), puis reboot
// pour reconnexion avec les nouveaux identifiants.
void on_ble_provisioning_credentials(const String& ssid, const String& pwd) {
  set_str_value(ap1_ssid, sizeof(ap1_ssid), ssid);
  // Le mot de passe peut être vide (réseau ouvert) : on l'accepte.
  strncpy(ap1_pwd, pwd.c_str(), sizeof(ap1_pwd) - 1);
  ap1_pwd[sizeof(ap1_pwd) - 1] = '\0';
  save_configuration();
  Serial.print("BLE provisioning : identifiants sauvegardés (ap1_ssid=");
  Serial.print(ap1_ssid);
  Serial.println("). Redémarrage pour reconnexion...");
  bleProv.notifyStatus("SUCCESS:rebooting");
  delay(500);
  bleProv.stop();
  delay(200);
  ESP.restart();
}

void reboot(Stream& stream) {
  send_response(stream, "reboot", "status=success");
  delay(100);
  ESP.restart();
}

const char* get_configuration() {
  snprintf(arg_short_response,
           sizeof(arg_short_response),
           "sensor_type=%s;sensor_id=%s;ap1_ip=%s;ap2_ip=%s;wifi_timeout=%d;loop_period=%d;current_ip=%s",
           sensor_type, sensor_id, ap1_ip, ap2_ip, wifi_timeout, loop_period, current_ip.toString().c_str());
  return arg_short_response;
}

const char* get_ap_configuration() {
  snprintf(arg_short_response,
           sizeof(arg_short_response),
           "ap1_ssid=%s;ap1_pwd=%s;ap2_ssid=%s;ap2_pwd=%s",
           ap1_ssid, ap1_pwd, ap2_ssid, ap2_pwd);
  return arg_short_response;
}

void dispatch_command(Stream& stream, CommandSource source, const String& line) {
  command.parse(line);
  const String& cmd = command.getCommand();
  if ((cmd == "set_ap_configuration" || cmd == "get_ap_configuration") && source != CommandSource::SerialOnly) {
    send_response(stream, cmd.c_str(), "status=error;error=serial_only_command");
    return;
  }
  if (cmd == "get_data") {
    send_response(stream, "get_data", _sensor->read_data());
  } else if (cmd == "set_configuration") {
    set_configuration(stream, command);
  } else if (cmd == "set_ap_configuration") {
    set_ap_configuration(stream, command);
  } else if (cmd == "get_ap_configuration") {
    send_response(stream, "get_ap_configuration", get_ap_configuration());
  } else if (cmd == "get_configuration") {
    send_response(stream, "get_configuration", get_configuration());
  }
  else if (cmd == "reboot") {
    reboot(stream);
  } else {
    send_response(stream, cmd.c_str(), "status=error;error=unknown_command");
  }
}

void handle_tcp_data() {
  if (!tcp_data_client || !tcp_data_client.connected()) {
    if (tcp_data_client) tcp_data_client.stop();
    tcp_data_client = tcpDataServer.available();
    if (tcp_data_client)
      Serial.println("TCP data client connected.");
  }
  if (!tcp_data_client || !tcp_data_client.connected()) return;
  uint16_t len;
  uint8_t* buffer = _sensor->get_data_frame(len);
  if (!buffer) return;
  if (tcp_data_client.write(buffer, len) != len) {
    Serial.println("TCP data send failed.");
    tcp_data_client.stop();
  }
}

void handle_serial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      dispatch_command(Serial, CommandSource::SerialOnly, serial_buffer);
      serial_buffer = "";
    } else {
      serial_buffer += c;
    }
  }
}

void handle_tcp() {
  if (!client || !client.connected()) {
    if (client)
      client.stop();
    client = tcpServer.available();
  }
  if (client && client.connected()) {
    while (client.available()) {
      char c = client.read();
      if (c == '\n') {
        dispatch_command(client, CommandSource::Tcp, tcp_buffer);
        tcp_buffer = "";
      } else {
        tcp_buffer += c;
      }
    }
  }
}

void handle_discovery() {
  int packet_size = discovery_udp.parsePacket();
  if (packet_size <= 0)
    return;

  char incoming[32] = {0};
  int len = discovery_udp.read(incoming, sizeof(incoming) - 1);
  incoming[len] = '\0';

  // rtrim si besoin :
  for (int i = len - 1; i >= 0 && (incoming[i] == '\r' || incoming[i] == '\n'); i--)
    incoming[i] = '\0';
  Serial.print("reçu UDP datagram sur port 5679:");
  Serial.println(incoming);
  if (strcmp(incoming, "mir_discover_request") != 0)
    return;

  IPAddress sender_ip = discovery_udp.remoteIP();
  char response[128];
  snprintf(response, sizeof(response),
           "{\"id\":\"%s\",\"type\":\"%s\",\"ip\":\"%s\"}",
           sensor_id, sensor_type, current_ip.toString().c_str());

  discovery_udp.beginPacket(sender_ip, DISCOVERY_RESPONSE_PORT);
  discovery_udp.write((const uint8_t*)response, strlen(response));
  discovery_udp.endPacket();
}

void setup() {
  Serial.begin(115200);

  load_configuration();
  print_configuration();
  // Provisioning BLE démarré AVANT la connexion WiFi pour fonctionner
  // en parallèle du point d'accès actuel (fenêtre de 60 s après le boot).
  bleProv.onCredentials(on_ble_provisioning_credentials);
  bleProv.begin("MIR_ESP_SENSOR");
  wifi_connected = connect_to_ap(ap1_ssid, ap1_pwd, ap1_ip);
  if (!wifi_connected)
    wifi_connected = connect_to_ap(ap2_ssid, ap2_pwd, ap2_ip);

  if (!wifi_connected) {
    Serial.println("Failed to connect to Wifi.");
    return;
  }
  Serial.print("Connected to Wifi. IP : ");
  current_ip = WiFi.localIP();
  Serial.println(current_ip.toString());

  tcpServer.begin();
  tcpServer.setNoDelay(true);
  Serial.print("TCP server started on port : ");
  Serial.println(TCP_PORT);

  tcpDataServer.begin();
  tcpDataServer.setNoDelay(true);
  Serial.print("TCP data server started on port : ");
  Serial.println(TCP_DATA_PORT);

  discovery_udp.begin(DISCOVERY_LISTEN_PORT);
  Serial.print("Discovery UPD listening on port:");  
  Serial.println(DISCOVERY_LISTEN_PORT);

  //déplacé l'initialisation du capteur, pour lui laisser du temps supplémentaire 
  //pour s'initialiser
  Serial.println("initializing sensor...");
  if (_sensor->init())
    Serial.println("sensor initialized.");
  else
    Serial.println("sensor failed to initialize.");


  test();
}

void loop() {
  static TickType_t last_wake = xTaskGetTickCount();
  vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(loop_period));
  bleProv.handle();
  _sensor->update_data();
  handle_serial();
  if(wifi_connected) {
    handle_tcp_data();
    handle_tcp();
    handle_discovery();
  }
}

