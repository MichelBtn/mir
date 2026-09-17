# Procédure d’installation de LeRobot (Hugging Face) sous Windows

Ce document détaille l'installation pas à pas du projet **LeRobot** (Hugging Face) sous l'environnement Windows en utilisant **Miniforge** (Conda) et **Git**.

---

## Étape Préalable : Installation de Git

Pour pouvoir cloner le dépôt LeRobot, **Git** doit être installé sur votre système Windows.

### Via l'installateur officiel (Recommandé)
1. Téléchargez l'installateur pour Windows sur le site officiel : [git-scm.com/download/win](https://git-scm.com/download/win).
2. Lancez le fichier `.exe` et suivez l'assistant d'installation en conservant les options par défaut.

---

## Étape 1 : Installation de Miniforge

1. Téléchargez l'installateur officiel Windows depuis le dépôt GitHub :
   [Miniforge3-Windows-x86_64.exe](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe)
2. Exécutez le fichier `.exe` téléchargé et suivez les instructions (les options par défaut conviennent).
3. Une fois l'installation terminée, ouvrez l'application **Miniforge Prompt** (ou **Miniforge CMD**) depuis le menu Démarrer.  
(il sera par la suite recommandé de passer par Miniforge prompt pour toutes les actions dans le terminal)
---

## Étape 2 : Configuration de l'environnement virtuel

Dans le terminal **Miniforge Prompt**, exécutez les commandes suivantes :

```cmd
:: 1. Création de l'environnement nommé 'lerobot' avec Python 3.12
conda create -y -n lerobot python=3.12

:: 2. Activation de l'environnement
conda activate lerobot

:: 3. Installation de ffmpeg
conda install ffmpeg=7.1.1 -c conda-forge
```

*Explications :*
L'activation de l'environnement modifie temporairement la variable `PATH`. Les commandes et exécutables (`python.exe`, `pip.exe`, `ffmpeg.exe`) pointeront désormais vers le dossier dédié de l'environnement `lerobot`.

---

## Étape 3 : Installation de LeRobot

Toujours dans le terminal **Miniforge Prompt** (avec l'environnement `(lerobot)` actif) :

1. **Cloner le dépôt officiel :**
   ```cmd
   git clone https://github.com/huggingface/lerobot.git
   cd lerobot
   ```

2. **Installer le paquet :**
   * *Option A : Installation en mode éditable (recommandée si vous modifiez le code source)*
     ```cmd
     pip install -e .
     ```
   * *Option B : Installation standard*
     ```cmd
     pip install lerobot
     ```

3. **Installations optionnelles (Extra Features) :**
   ```cmd
   :: Pour les moteurs Feetech
   pip install -e ".[feetech]"

   :: Pour les environnements Aloha et Pusht
   pip install -e ".[aloha,pusht]"

   :: Pour installer l'ensemble des fonctionnalités optionnelles
   pip install -e ".[all]"
   ```

---

## Arborescence et emplacements sous Windows

Pour afficher l'emplacement de vos environnements Conda, lancez :
```cmd
conda env list
```

Sur Windows, l'environnement se trouve généralement dans :
`C:\Users\<VotreNomDeSession>\miniforge3\envs\lerobot`

* **Modules Python (`pip install`) :**
  `C:\Users\<VotreNomDeSession>\miniforge3\envs\lerobot\Lib\site-packages\`
* **Exécutables (`python.exe`, `ffmpeg.exe`, etc.) :**
  `C:\Users\<VotreNomDeSession>\miniforge3\envs\lerobot\` (ou `...\envs\lerobot\Scripts\`)

---

## Configuration et utilisation dans VS Code

Pour travailler directement dans Visual Studio Code sans passer par le raccourci *Miniforge Prompt* du menu Démarrer :

1. Ouvrez votre dossier projet `lerobot` dans VS Code.
2. Appuyez sur `Ctrl + Shift + P` → Sélectionnez **Python: Select Interpreter**.
3. Choisissez l'interpréteur lié à votre environnement Conda :
   `C:\Users\<VotreNomDeSession>\miniforge3\envs\lerobot\python.exe`
4. Ouvrez un terminal dans VS Code (`Ctrl + ` ` ` ` ou **Terminal** → **Nouveau terminal**).
5. Si `conda` n'est pas activé automatiquement dans le terminal VS Code, activez-le manuellement en lançant :
   ```cmd
   C:\Users\<VotreNomDeSession>\miniforge3\Scripts\activate lerobot
   ```
   *(Pensez à remplacer `<VotreNomDeSession>` par votre nom d'utilisateur Windows, par exemple `Michel`).*

---

## Annexe

### Pourquoi faut-il passer par le Miniforge Prompt sous Windows et pas sous Linux ?

* **Sous Linux :** Lors de l'installation de Miniforge/Conda, un script modifie le fichier de configuration du shell (`~/.bashrc` ou `~/.zshrc`). Ainsi, dès que vous ouvrez n'importe quel terminal standard, la commande `conda` est directement disponible et la commande `conda activate lerobot` fonctionne immédiatement.
* **Sous Windows :** Pour éviter de polluer les variables d'environnement système globales (PATH) et risquer d'entrer en conflit avec d'autres programmes ou d'autres versions de Python, l'installateur Miniforge n'ajoute pas `conda` automatiquement au terminal Windows standard (CMD / PowerShell). À la place, il fournit le raccourci **Miniforge Prompt**, qui est une invite de commandes pré-initialisée avec l'accès aux commandes Conda.

### Comment tout faire depuis le terminal de VS Code ?

VS Code utilise par défaut le terminal système (PowerShell ou Command Prompt). Pour exécuter l'étape 3 directement dans VS Code :
1. Vous devez vous assurer que l'environnement est actif dans le terminal du bas. Vous devez voir `(lerobot)` en début de ligne.
2. Si `(lerobot)` n'apparaît pas, exécutez le script d'activation de Conda avec son chemin complet :
   `C:\Users\<VotreNomDeSession>\miniforge3\Scripts\activate lerobot`
3. Dès que `(lerobot)` s'affiche, toutes vos commandes (`git clone`, `pip install`, etc.) cibleront l'environnement virtuel isolé.
