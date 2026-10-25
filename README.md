# Spiderbot

Pilotage d'une araignée robot à six pattes [Freenove Hexapod Robot](https://github.com/Freenove/Freenove_Hexapod_Robot_Kit)
(Arduino Mega 2560) depuis un serveur Linux, par USB ou par wifi, en réutilisant le protocole
de commandes du programme d'origine Freenove.

> En construction : pilotage par USB seulement, le wifi viendra ensuite.

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
$ spiderbot avance 3
Avance : 3 pas
```

| Commande | Effet |
|---|---|
| `etat`, `batterie` | Le robot répond-il ? Tension et état des batteries |
| `avance`, `recule`, `gauche`, `droite` `[pas]` | Marcher, 1 à 20 pas (1 par défaut) |
| `tourne gauche\|droite [pas]` | Tourner sur place |
| `hauteur <0..45>` | Hauteur du corps, en mm |
| `penche <x> <y> <z>` | Pencher le corps, en degrés (15° en tout au plus) |
| `decale <x> <y> <z>` | Décaler le corps sans marcher : x et y en mm (±20), z hauteur (0 à 45) |
| `couche`, `reveille` | Se coucher (repos), se mettre debout |

La carte est trouvée toute seule par son identifiant USB, ou désignée avec `--port`. Si le
robot ne répond pas, la commande rend la main en moins de 5 secondes avec un message.

- **Valeurs** : vérifiées avant tout envoi, avec un message en cas d'erreur.
- **Batteries** : la tension est lue avant chaque mouvement. Sous le seuil « trop faible »,
  les mouvements sont refusés, mais `couche`, `batterie` et `etat` restent possibles.
- **Arrêt** : le protocole d'origine n'a pas d'ordre « stop », et le robot ignore tout ordre
  pendant un mouvement. La marche se fait donc un pas à la fois, et **Ctrl+C laisse finir le
  pas en cours**, puis s'arrête, le robot debout. Un second Ctrl+C rend la main sans attendre.
- **Démarrage** : ouvrir le port série redémarre la carte, et son chargeur de démarrage se
  bloque pour de bon s'il reçoit un octet dans la première seconde. La commande se tait donc
  1,5 s avant de parler au robot.

## Tests

```bash
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

Les tests n'ont pas besoin du robot : un robot simulé parle le même protocole sur un faux
port série (pseudo-terminal). Il reproduit le piège du chargeur de démarrage, la durée des
mouvements et les ordres ignorés pendant un mouvement.

## Prévu

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
