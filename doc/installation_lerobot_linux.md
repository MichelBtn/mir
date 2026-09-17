# Procédure d’installation de LeRobot (Hugging Face) sous Linux

Ce document détaille l'installation pas à pas du projet **LeRobot** (Hugging Face) sous l'environnement Linux en utilisant **Miniforge** (Conda) et **Git**.

---

## Étape Préalable : Installation de Git

Pour pouvoir cloner le dépôt LeRobot, **Git** doit être installé sur votre système Linux.

### Via le gestionnaire de paquets (ex. Ubuntu / Debian)
```bash
sudo apt update
sudo apt install -y git wget
```

---

## Étape 1 : Installation de Miniforge

1. Téléchargez et exécutez le script d'installation officiel via votre terminal :
   ```bash
   wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
   bash Miniforge3-$(uname)-$(uname -m).sh
   ```
2. Suivez les instructions à l'écran (validez la licence puis acceptez l'emplacement par défaut).
3. À la fin de l'installation, acceptez l'initialisation de Conda (`conda init`).

---

## Étape 2 : Configuration de l'environnement virtuel

Dans votre terminal Linux, exécutez les commandes suivantes :

```bash
# 1. Création de l'environnement nommé 'lerobot' avec Python 3.12
conda create -y -n lerobot python=3.12

# 2. Activation de l'environnement
conda activate lerobot

# 3. Installation de ffmpeg
conda install ffmpeg=7.1.1 -c conda-forge
```

*Explications :*
L'activation de l'environnement modifie les variables d'environnement du shell, notamment `PATH`. Les commandes et exécutables (`python`, `pip`, `ffmpeg`) pointeront désormais vers le dossier où sont installées les dépendances LeRobot.

---

## Étape 3 : Installation de LeRobot

Dans votre terminal (avec l'environnement `(lerobot)` actif) :

1. **Cloner le dépôt officiel :**
   ```bash
   git clone https://github.com/huggingface/lerobot.git
   cd lerobot
   ```

2. **Installer le paquet :**
   * *Option A : Installation en mode éditable (recommandée si vous modifiez le code source)*
     ```bash
     pip install -e .
     ```
   * *Option B : Installation standard*
     ```bash
     pip install lerobot
     ```

3. **Installations optionnelles (Extra Features) :**
   ```bash
   # Pour les moteurs Feetech
   pip install -e ".[feetech]"

   # Pour les environnements Aloha et Pusht
   pip install -e ".[aloha,pusht]"

   # Pour installer l'ensemble des fonctionnalités optionnelles
   pip install -e ".[all]"
   ```

---

## Arborescence et emplacements sous Linux

Pour afficher l'emplacement de vos environnements Conda, lancez :
```bash
conda env list
```

Sous Linux, l'environnement se trouve généralement dans :
`/home/$USER/miniforge3/envs/lerobot`

* **Modules Python (`pip install`) :**
  `/home/$USER/miniforge3/envs/lerobot/lib/python3.12/site-packages/`
* **Exécutables (`python`, `ffmpeg`, etc.) :**
  `/home/$USER/miniforge3/envs/lerobot/bin/`

---

## Configuration et utilisation dans VS Code

Pour travailler directement dans Visual Studio Code sous Linux :

1. Ouvrez votre dossier projet `lerobot` dans VS Code (`code .`).
2. Appuyez sur `Ctrl + Shift + P` → Sélectionnez **Python: Select Interpreter**.
3. Choisissez l'interpréteur lié à votre environnement Conda :
   `/home/$USER/miniforge3/envs/lerobot/bin/python`
4. Ouvrez un terminal dans VS Code (`Ctrl + ` ` ` ` ou **Terminal** → **Nouveau terminal**).
5. Si l'environnement n'est pas activé automatiquement, lancez :
   ```bash
   conda activate lerobot
   ```

