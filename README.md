# Spiderbot

Pilotage d'une araignée robot à six pattes [Freenove Hexapod Robot](https://github.com/Freenove/Freenove_Hexapod_Robot_Kit)
(Arduino Mega 2560) depuis un serveur Linux, par USB ou par wifi, en réutilisant le protocole
de commandes du programme d'origine Freenove.

> En construction : seules les commandes `etat` et `batterie` existent pour l'instant, par USB.

## Installation

Python 3.14 ou plus récent :

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Le compte doit avoir accès au port série : `sudo usermod -aG dialout $USER`, puis se
reconnecter. Réglages facultatifs : copier `config.exemple.toml` dans
`~/.config/spiderbot/config.toml`.

## Utilisation

```console
$ spiderbot etat
Robot présent sur /dev/ttyACM0 (réponse en 1,6 s)
$ spiderbot batterie
Batterie : 7,84 V (ok)
```

La carte est trouvée toute seule par son identifiant USB, ou désignée avec `--port`. Si le
robot ne répond pas, la commande rend la main en moins de 5 secondes avec un message.

À savoir : ouvrir le port série redémarre la carte, et son chargeur de démarrage se bloque
pour de bon s'il reçoit un octet dans la première seconde. La commande se tait donc 1,5 s
avant de parler au robot.

## Tests

```bash
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

Les tests n'ont pas besoin du robot : un robot simulé parle le même protocole sur un faux
port série (pseudo-terminal), y compris le piège du chargeur de démarrage.

## Prévu

- D'autres commandes : avancer, tourner, postures, coucher
- Des gestes décrits dans de simples fichiers : saluer, danser…
- Une retouche de la bibliothèque Freenove pour que le robot rejoigne un wifi existant tout en
  gardant son propre point d'accès

## Matériel

| Élément | Carte | Liaison |
|---|---|---|
| Robot (18 servos) | Arduino Mega 2560 + ESP8266 | wifi, radio nRF24L01, USB |
| Manette | Arduino Uno R3 + Freenove Smart Car Remote Shield | radio nRF24L01 |

## Licence

[MIT](LICENSE). Les parties reprises de la bibliothèque Freenove restent sous leur licence
d'origine, CC BY-SA 3.0.
