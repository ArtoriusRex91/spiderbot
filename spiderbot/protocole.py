"""Protocole de commandes du programme d'origine Freenove (FNHROrders.h).

Une trame : [128] [ordre] [donnée 0] … [donnée n] [129]. L'ordre et les données vont de 0 à
127 ; les valeurs signées sont décalées de +64. Le robot répond à chaque ordre par une trame.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

DEBUT = 128
FIN = 129

# Ordres utilisés (les pairs sont envoyés, les impairs sont des réponses)
DEMANDE_ECHO = 0
ECHO = 1
DEMANDE_TENSION = 10
TENSION = 11
ORDRE_COMMENCE = 21
ORDRE_FINI = 23


class ErreurProtocole(Exception):
    """Trame invalide, reçue ou à envoyer."""


def trame(ordre: int, *donnees: int) -> bytes:
    """Construit une trame à envoyer."""
    for valeur in (ordre, *donnees):
        if not 0 <= valeur <= 127:
            raise ErreurProtocole(f"valeur hors de 0..127 : {valeur}")
    return bytes([DEBUT, ordre, *donnees, FIN])


@dataclass(frozen=True)
class Reponse:
    ordre: int
    donnees: tuple[int, ...]


class Decodeur:
    """Reconstitue les trames dans un flux d'octets reçus par morceaux.

    Les octets hors trame (bruit au démarrage de la carte) sont ignorés, et un nouveau
    début de trame abandonne la trame incomplète en cours, comme le fait le robot.
    """

    def __init__(self) -> None:
        self._en_cours: list[int] | None = None

    def ajouter(self, octets: Iterable[int]) -> Iterator[Reponse]:
        for octet in octets:
            if octet == DEBUT:
                self._en_cours = []
            elif self._en_cours is None:
                continue
            elif octet == FIN:
                contenu, self._en_cours = self._en_cours, None
                if contenu:
                    yield Reponse(contenu[0], tuple(contenu[1:]))
            elif octet > 127:
                self._en_cours = None  # octet impossible dans une trame : on l'abandonne
            else:
                self._en_cours.append(octet)


def tension(reponse: Reponse) -> float:
    """Décode la réponse à une demande de tension, en volts."""
    if reponse.ordre != TENSION or len(reponse.donnees) != 2:
        raise ErreurProtocole(f"réponse de tension inattendue : {reponse}")
    haut, bas = reponse.donnees
    return (haut * 128 + bas) / 100
