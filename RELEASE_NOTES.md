##### 02/08/2026. image caméra dans la fenêtre de configuration (scan devices)

##### 02/08/2026. rotation de l'image caméra affichée
choix de rotation : 0 (par défaut), 90, 180, 270  

##### 01/08/2026. prise en compte d'un couple maximum
par défaut 250 (25%) lors de la création du bus moteur   
peut être modifié dans le fichier de configuration json

##### 01/08/2026. affichage d'unités dans les observations

##### 31/07/2026. Option "Charger la calibration depuis les moteurs"

##### 30/07/2026. Correctif : robot monitor/Actions, la consigne de position 0 n'était pas prise en compte

##### 29/07/2026. Utilitaire mir_esp_deploy.
mise à jour du firmware   
configuration des identifiants de points d'accès via la liaison série

##### 27/072026. ESP32 : configurer identifiants de points d'accès uniquement sur le port série.

##### 25/07/2026. correctif script de déploiement pi (mir_pi_sensors/deploy.sh)
le fichier setup_services.sh n'était pas copié   
le fichier requirements.in n'était pas copié

##### 24/07/2026. correctifs éditeur
le chemin du dialogue 'sauver' n'était pas toujours restauré   
l'état _configuration_dirty n'était pas correct après la sauvegarde d'une configuration scannée


##### 23/07/2026. robot_monitor : amélioré la disposition des ScopesWidget

##### 21/07/2026. refactoring important
introduction mirDevices qui centralise tous les devices (sensors et motor_bus)  
et gère les observations

##### 20/07/2026. génération des observations dans la fonction de scan
la liste des observations disponibles est affiché, l'utilisateur choisit celles qu'il retient

##### 18/07/2026. configuration des appareils
la fenêtre de scan intègre désormais la configuration des capteurs et des ids moteurs  

##### 18/07/2026. flag configuration_dirty : configuration enregistrée/non enregistrée

##### 15/7/2026. réinitialisation automatique des capteurs
fonctions de reset intégrée à pi_camera (redémarrage du service, pas besoin d'un reboot complet de l'OS)   
fonctions de reset intégrée eux eps (reboot du capteur)

##### 14/7/2026. fenêtre de configuration des capteurs
prise en charge partielle des esp32 et de picamera

##### 11/7/2026. refactoring important
implique une nouvelle structure des fichiers de configuration robot  
nécessite de redéployer le code des capteurs sur pi-zero (mir_pi_sensors/deploy.py)  
nécessite de mettre à jour le code des esp32

##### 10/7/2026. prise en charge des capteurs esp32 

##### 10/7/2026. intégration esp32/platformio au projet mir

##### 10/7/2026. correctif : une erreur était générée lors de la connexion au robot avec un configuration sans moteurs

##### 6/7/2026. ajustement des échelles verticales des scopes (velocity et position uniquement)

##### 6/7/2026. les valeurs de position en mode VELOCITY sont normalisées

##### 6/7/2026. lorsqu'on arrête les observations dans robot monitor, les mouvements en cours sont stoppés

##### 5/7/2026. les statistiques fps peuvent être activées/désactivées

##### 4/7/2026. connexion robot interdite si la calibration n'est pas valide

##### 4/7/2026. bouton d'arrêt d'urgence dans les actions
désactive les couples sur tous les moteurs
met les vitesses (Goal_Velocity) à 0 (d'où l'importance de registre Phase = 0)
met les positions (Goal_Position) sur les positions courantes

##### 4/7/2026. groupes d'actions dans robot monitor

##### 4/7/2026. prise en compte d'unités
pour la vitesse : toujours en RPM.   
pour la position : en 'degrés' si la calibration est valide, en 'pas' sinon.  
noter que seul norm_mode = DEGREES est actuellement supporté.

##### 4/7/2026. en mode POSITION les vitesses sont définies dans le fichier de configuration
Un champ position_mode_velocity, par défaut à 100 est ajouté à la configuration de chaque moteur.  
Les action_features du fichier de configuration sont ignorées, et construites en fonction de la configuration.  
Par exemple avec 3 moteurs 'joint1', 'joint2', 'joint3' respectivement en POSITION, POSITION, VELOCITY :  
```bash
action_features = {
    "joint1.position" : 'float',
    "joint2.position" : 'float',
    "joint3.velocity" : 'int',
}
```

##### 4/7/2026. le registre de phase est forcé à 0 au démarrage
plus précisément à chaque connexion du bus moteur et si la valeur courante est différente de 0. dans ce cas un warning est généré dans les logs

##### 3/7/2026. correctif : en mode AP, le scan des équipements wifi échouait sur une erreur 'Network unreachable'

##### 3/7/2026. intégré mir_ip_sensors au projet
mir_ip_sensors implémente le code des serveurs caméra et lidar sur le rapsberry pi zero 2w
et permet son déploiement sur le pi

##### 3/7/2026. dans robot monitor, la fréquence de boucle est réglable et des statistiques détaillées du fps sont disponibles

##### 3/7/2026. le registre feetech 'Moving_Velocity' en doublon de 'Moving_Velocity_Threshold' est supprimé

##### 2/7/2026. intégration des actions dans robot monitor

##### 1/7/2026. amélioration de l'éditeur de configuration
icones dans le treeview.  
éditeur de code json.






