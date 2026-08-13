## mir

### *M*odular *I*ntelligent *R*obot

### construisez votre robot en quelques clics

ceci est une version *theta* (claques) donc faisez attention, il risque d'y avoir des bugs, et ça peut casser des trucs.
OS supporté : Linux only

###
installation :  
cloner le dépot  
activer l'environnement conda lerobot  
depuis le dossier racine du projet, exécuter install.sh  

pour réutiliser la librairie mir_utils (pas de dépendance lerobot):   
pip install -e "git+ssh://git@github.com/MichelBtn/mir.git#subdirectory=mir_utils"   
ou en local, après installation comme ci-dessus :
pip install -e /chemin/local/mir/mir_utils   

## Citation

Ce projet utilise [LeRobot](https://github.com/huggingface/lerobot) de HuggingFace.
Si vous utilisez ce projet, merci de citer :

```bibtex
@misc{cadene2024lerobot,
    author = {Cadene, Remi and Alibert, Simon and Soare, Alexander and Gallouedec, Quentin and Zouitine, Adil and Palma, Steven and Kooijmans, Pepijn and Aractingi, Michel and Shukor, Mustafa and Aubakirova, Dana and Russi, Martino and Capuano, Francesco and Pascal, Caroline and Choghari, Jade and Moss, Jess and Wolf, Thomas},
    title = {LeRobot: State-of-the-art Machine Learning for Real-World Robotics in Pytorch},
    howpublished = "\url{https://github.com/huggingface/lerobot}",
    year = {2024}
}
```
