# Spiderbot

Pilotage d'une araignée robot à six pattes [Freenove Hexapod Robot](https://github.com/Freenove/Freenove_Hexapod_Robot_Kit)
(Arduino Mega 2560) depuis un serveur Linux, par USB ou par wifi, en réutilisant le protocole
de commandes du programme d'origine Freenove.

> En construction : rien n'est encore utilisable.

## Prévu

- Une commande en terminal : avancer, tourner, postures, coucher, tension des batteries
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
