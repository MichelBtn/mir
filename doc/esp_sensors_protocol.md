# Documentation du Protocole de Communication (`esp32_sensor`)

Ce document décrit en détail les protocoles d'échange et de communication exposés par le micrologiciel **`esp32_sensor`** (projet `mir`) à travers ses différents canaux d'E/S : Liaison série (UART), TCP texte (commandes), TCP binaire (flux de données capteur) et UDP (découverte réseau).

---

## 1. Vue d'ensemble des Transports & Canaux

Le système utilise 4 canaux de communication distincts :

| Transport | Port | Type / Format | Usage principal | Restrictif / Spécificité |
| :--- | :--- | :--- | :--- | :--- |
| **Liaison Série** | — (UART) | Texte ASCII (`\n`) | Configuration initiale, diagnostic, gestion WiFi | **Accès complet** (Credentials WiFi autorisés) |
| **TCP Commandes**| `5000` | Texte ASCII (`\n`) | Configuration à distance, interrogation | **Restreint** (Credentials WiFi interdits) |
| **TCP Données** | `5001` | Binaire (Little-Endian) | Stream haute fréquence des données capteur | Flux binaire continu orienté trames |
| **UDP Découverte**| `5679` (In)<br>`5678` (Out) | Texte ASCII / JSON | Auto-découverte des modules sur le réseau | Détection dynamique de l'IP du module |

### Paramètres Série
- **Baudrate** : `115200` baud
- **Format** : 8 bits de données, pas de parité, 1 bit de stop (8N1)
- **Délimiteur de ligne** : `\n` (Line Feed, ASCII `0x0A`)

---

## 2. Protocole de Commandes Texte (Série & TCP Port 5000)

Le protocole de commande est un protocole ASCII synchrone basé sur des lignes terminées par `\n`. Il est identique sur la liaison Série et le serveur TCP port 5000, à l'exception de la politique de sécurité restreignant les identifiants WiFi sur TCP.

### 2.1. Format des Requêtes
```text
<commande> <cle1>=<valeur1>;<cle2>=<valeur2>\n
```
- **Nom de la commande** : Premier mot (séparé des arguments par un espace).
- **Arguments** : Paires `clé=valeur` séparées par des points-virgules `;`.
- **Limites système** :
  - Taille maximale du buffer d'entrée : **1000 octets** (`CMD_BUFFER_SIZE`).
  - Nombre maximal d'arguments par commande : **10** (`CMD_MAX_ARGS`).

### 2.2. Format des Réponses
Toute réponse est préfixée par le caractère `#` suivi du nom de la commande réceptrice :
```text
#<commande> <cle1>=<valeur1>;<cle2>=<valeur2>\n
```

- **En cas de succès d'une commande d'action** :
  ```text
  #<commande> status=success\n
  ```
- **En cas d'erreur** :
  ```text
  #<commande> status=error;error=<motif_erreur>\n
  ```

#### Codes d'erreur standards :
- `unknown_command` : Commande non reconnue par le système.
- `serial_only_command` : Tentative d'exécution d'une commande réservée à la liaison série depuis un socket TCP.

---

### 2.3. Répertoire des Commandes

#### A. Commandes de Données (Série et TCP)

##### `get_data`
Demande la dernière mesure du capteur au format texte ASCII.
- **Requête** : `get_data\n`
- **Réponse** : `#get_data <valeurs_ASCII>\n`
- **Format du payload selon le capteur activé (`sensor_type`)** :
  - **`esp_simulation` / `simulation`** :
    ```text
    #get_data <timestamp_us>;<omega>;<theta>
    ```
    *(Exemple : `#get_data 12345678;0.500;-0.250`)*
  - **`esp_wheather` / `wheather`** :
    ```text
    #get_data <timestamp_us>;<temperature_C>;<humidité_relative_%_entier>
    ```
    *(Exemple : `#get_data 12345678;23.5;45`)*
  - **`esp_lidar` / `lidar`** :
    ```text
    #get_data lidar: use TCP data stream on port 5001
    ```

---

#### B. Configuration Générale (Série et TCP)

##### `get_configuration`
Lit les paramètres de configuration du système (hors identifiants WiFi sensibles).
- **Requête** : `get_configuration\n`
- **Réponse** :
  ```text
  #get_configuration sensor_type=<type>;sensor_id=<id>;ap1_ip=<ip>;ap2_ip=<ip>;wifi_timeout=<sec>;loop_period=<ms>;current_ip=<ip>\n
  ```

##### `set_configuration`
Met à jour un ou plusieurs paramètres système et les sauvegarde en mémoire non volatile (NVS namespace `sensor_cfg`).
- **Requête** : `set_configuration <cle>=<valeur>;...\n`
- **Champs modifiables** :

| Clé | Type / Format | Description / Contraintes |
| :--- | :--- | :--- |
| `sensor_type` | Chaîne | Type de capteur (`simulation`, `lidar`, `wheather`). |
| `sensor_id` | Chaîne (≤ 31 chars) | Identifiant unique du nœud. |
| `ap1_ip` | IPv4 ou `auto` | Adresse IP statique pour l'AP 1 (`auto` = DHCP). |
| `ap2_ip` | IPv4 ou `auto` | Adresse IP statique pour l'AP 2 (`auto` = DHCP). |
| `wifi_timeout` | Entier (≥ 2) | Délai d'attente de connexion WiFi en secondes (défaut : 5s). |
| `loop_period` | Entier (`10 <= x < 1000`) | Période d'exécution de la boucle principale en ms (défaut : 25ms). |

- **Réponse** :
  ```text
  #set_configuration status=success\n
  ```

---

#### C. Configuration WiFi & Sécurité (**Liaison Série UNIQUEMENT**)

Pour éviter que des identifiants réseau ne transitent en clair sur le réseau sans fil, les commandes ci-dessous sont **strictement rejetées lorsqu'elles sont reçues via TCP**.

##### `get_ap_configuration`
- **Port autorisé** : **Série uniquement**
- **Requête** : `get_ap_configuration\n`
- **Réponse sur Série** :
  ```text
  #get_ap_configuration ap1_ssid=<ssid1>;ap1_pwd=<pwd1>;ap2_ssid=<ssid2>;ap2_pwd=<pwd2>\n
  ```
- **Réponse si exécutée via TCP** :
  ```text
  #get_ap_configuration status=error;error=serial_only_command\n
  ```

##### `set_ap_configuration`
- **Port autorisé** : **Série uniquement**
- **Requête** : `set_ap_configuration ap1_ssid=<ssid1>;ap1_pwd=<pwd1>;ap2_ssid=<ssid2>;ap2_pwd=<pwd2>\n`
- **Réponse sur Série** :
  ```text
  #set_ap_configuration status=success\n
  ```
- **Réponse si exécutée via TCP** :
  ```text
  #set_ap_configuration status=error;error=serial_only_command\n
  ```

---

#### D. Système (Série et TCP)

##### `reboot`
Provoque le redémarrage logiciel de l'ESP32.
- **Requête** : `reboot\n`
- **Réponse** : `#reboot status=success\n` *(envoyée 100 ms avant la réinitialisation matérielle)*.

---

## 3. Protocole TCP Flux de Données Binaires (TCP Port 5001)

Le port TCP `5001` est dédié au streaming haute fréquence et bas niveau des trames de données capteur. Toutes les valeurs multi-octets sont codées en **Little-Endian**.

### 3.1. Structure d'une Trame Binaire

Chaque trame transmise sur la socket binaire commence par un **en-tête fixe de 14 octets** suivi du **payload de données** dépendant du capteur activé.

```
+-------------------------------------------------------------------------------+
|                        EN-TÊTE FIXE (14 octets)                               |
+---------------+---------------+-------------------------------+---------------+
| Magic 0 (1B)  | Magic 1 (1B)  | Sequence Number (4B, uint32)  | Timestamp (8B)|
| 0xA5          | 0x5A          | Incrémenté à chaque trame     | Horodatage µs |
+---------------+---------------+-------------------------------+---------------+
|                               PAYLOAD SPÉCIFIQUE AU CAPTEUR                   |
+-------------------------------------------------------------------------------+
```

#### Détail de l'En-tête Fixe (14 octets) :

| Octets | Type | Champ | Description / Valeur |
| :--- | :--- | :--- | :--- |
| `0` | `uint8_t` | `MAGIC_0` | Octet de synchronisation 1 : `0xA5` |
| `1` | `uint8_t` | `MAGIC_1` | Octet de synchronisation 2 : `0x5A` |
| `2..5` | `uint32_t` | `sequence` | Compteur de trames incrémenté à chaque envoi (0, 1, 2, ...). |
| `6..13` | `uint64_t` | `timestamp` | Temps système écoulé depuis le démarrage en **microsecondes** (`esp_timer_get_time()`). |

---

### 3.2. Formats du Payload selon le Capteur

#### A. Capteur Simulation (`SensorSimulation`)
- **Taille du payload** : 10 octets (`data_len` + `omega` + `theta`)
- **Taille totale de la trame binaire** : **24 octets** (14 + 10)

| Octets | Type | Champ | Description |
| :--- | :--- | :--- | :--- |
| `14..15` | `uint16_t` | `data_len` | Nombre d'éléments / longueur symbolique (Valeur fixe = `2`) |
| `16..19` | `float` (IEEE 754) | `omega` | Vitesse angulaire simulée (rad/s) |
| `20..23` | `float` (IEEE 754) | `theta` | Angle simulé (rad) |

#### B. Capteur Météo (`SensorWheather` - AHTX0)
- **Taille du payload** : 10 octets (`data_len` + `temperature` + `rel_humidity`)
- **Taille totale de la trame binaire** : **24 octets** (14 + 10)

| Octets | Type | Champ | Description |
| :--- | :--- | :--- | :--- |
| `14..15` | `uint16_t` | `data_len` | Longueur symbolique (Valeur fixe = `4`) |
| `16..19` | `float` (IEEE 754) | `temperature` | Température mesurée en **°C** |
| `20..23` | `float` (IEEE 754) | `rel_humidity` | Humidité relative mesurée en **%** |

#### C. Capteur LIDAR (`SensorLidar` - RPLIDAR C1)
- **Taille du payload** : `2 + (N × 5)` octets (où $N$ est le nombre de points dans le scan, $N \le 500$)
- **Taille totale de la trame binaire** : `16 + (N × 5)` octets (14 + 2 + $N \times 5$)

| Octets | Type | Champ | Description |
| :--- | :--- | :--- | :--- |
| `14..15` | `uint16_t` | `count` | Nombre de points de mesure $N$ contenus dans la trame. |
| `16 .. 15+(N*5)`| `ScanPoint[N]` | `points` | Tableau de $N$ structures compactées `ScanPoint` (5 octets / point). |

##### Structure d'un `ScanPoint` (`__attribute__((packed))`, 5 octets) :

| Décalage relatif | Type | Champ | Description / Unité |
| :--- | :--- | :--- | :--- |
| `+0` | `uint8_t` | `quality` | Qualité / intensité de réflexion du signal (`0` à `255`). |
| `+1..+2` | `uint16_t` | `angle` | Angle mesuré en **dixièmes de degré** (`0` à `3599` pour $0,0^\circ \dots 359,9^\circ$). |
| `+3..+4` | `uint16_t` | `distance` | Distance mesurée en **centimètres** (`0` = mesure invalide/hors portée). |

---

## 4. Protocole de Découverte Network UDP (Port 5679 / 5678)

L'ESP32 écoute sur le réseau local pour répondre automatiquement aux requêtes d'auto-découverte émises par les clients (ex. applications hôtes, robots, interfaces de contrôle).

```
   Client (Application Hôte)                    ESP32 (Capteur Nœud)
               |                                         |
               | --- Datagramme UDP (Port 5679) --------> |
               |     "mir_discover_request"              |
               |                                         |
               | <--- Réponse UDP (Port 5678) ----------- |
               |      JSON payload                       |
```

### 4.1. Requête de Découverte (Client $\to$ ESP32)
- **Port de destination ESP32** : UDP `5679`
- **Contenu du datagramme** : Chaîne ASCII exacte `"mir_discover_request"` (les fin de lignes `\r` ou `\n` sont ignorées).

### 4.2. Réponse de Découverte (ESP32 $\to$ Client)
- **Port de destination Client** : UDP `5678` (envoyé directement à l'IP émettrice de la requête UDP).
- **Format du payload** : Objet JSON au format ASCII texte.

#### Exemple de payload JSON retourné :
```json
{
  "id": "esp_0",
  "type": "esp_lidar",
  "ip": "192.168.1.42"
}
```

---

## 5. Résumé des Séquences et Exemples d'Échanges

### Exemple 1 : Lecture de la configuration via TCP (Port 5000)
**Client $\to$ ESP32 (Port 5000)** :
```text
get_configuration\n
```
**ESP32 $\to$ Client** :
```text
#get_configuration sensor_type=lidar;sensor_id=esp_0;ap1_ip=192.168.1.42;ap2_ip=auto;wifi_timeout=5;loop_period=25;current_ip=192.168.1.42\n
```

### Exemple 2 : Tentative de modification des mots de passe WiFi via TCP (Port 5000)
**Client $\to$ ESP32 (Port 5000)** :
```text
set_ap_configuration ap1_ssid=MonReseau;ap1_pwd=Secret123\n
```
**ESP32 $\to$ Client (Refusé par sécurité)** :
```text
#set_ap_configuration status=error;error=serial_only_command\n
```

### Exemple 3 : Définition des identifiants WiFi via Liaison Série (UART)
**Terminal $\to$ ESP32 (Série)** :
```text
set_ap_configuration ap1_ssid=MonReseau;ap1_pwd=Secret123\n
```
**ESP32 $\to$ Terminal** :
```text
#set_ap_configuration status=success\n
```

---
*Document généré automatiquement d'après l'analyse du code source du projet `esp32_sensor`.*
