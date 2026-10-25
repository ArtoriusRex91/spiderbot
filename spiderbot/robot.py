"""Les mouvements du robot : limites, réveil, sécurité batterie, marche pas à pas.

Le protocole d'origine n'a pas d'ordre « stop », et le robot ignore tout ordre reçu pendant
un mouvement. La marche se fait donc un pas à la fois : chaque pas est un ordre bloquant
dont on attend la fin avant d'envoyer le suivant. Ctrl+C laisse finir le pas en cours,
puis plus rien n'est envoyé : le robot reste debout.
"""

import math
import signal
from collections.abc import Callable
from types import FrameType

from . import protocole
from .reglages import Reglages
from .transport import ErreurRobot, RobotMuet, TransportUSB

PAS_MAX = 20
HAUTEUR = (0, 45)  # mm au-dessus de la position basse (le robot borne aussi à 0..45)
PENCHE_MAX = 15  # degrés : le robot borne l'inclinaison totale à 15°
DECALE_MAX = 20  # mm pour x et y (le robot accepte jusqu'à 30)
FIN_MOUVEMENT = 10.0  # secondes : au-delà, on considère que le mouvement ne finira pas

MARCHES = {
    "avance": protocole.AVANCE,
    "recule": protocole.RECULE,
    "gauche": protocole.GAUCHE,
    "droite": protocole.DROITE,
    "tourne gauche": protocole.TOURNE_GAUCHE,
    "tourne droite": protocole.TOURNE_DROITE,
}


class ErreurValeur(Exception):
    """Valeur refusée avant tout envoi au robot."""


class Interrompu(Exception):
    """Ctrl+C : le robot a fini son pas en cours et s'est arrêté."""

    def __init__(self, faits: int, prevus: int) -> None:
        super().__init__(f"{faits} pas sur {prevus}")
        self.faits = faits
        self.prevus = prevus


# --- Vérification des valeurs, avant toute ouverture du port ------------------------------


def entier(texte: str, nom: str) -> int:
    try:
        return int(texte)
    except ValueError:
        raise ErreurValeur(f"{nom} doit être un nombre entier, pas « {texte} »") from None


def verifier_pas(texte: str | None) -> int:
    if texte is None:
        return 1
    pas = entier(texte, "Le nombre de pas")
    if not 1 <= pas <= PAS_MAX:
        raise ErreurValeur(f"Le nombre de pas doit être compris entre 1 et {PAS_MAX}")
    return pas


def verifier_hauteur(texte: str) -> int:
    hauteur = entier(texte, "La hauteur")
    if not HAUTEUR[0] <= hauteur <= HAUTEUR[1]:
        raise ErreurValeur(f"La hauteur doit être comprise entre {HAUTEUR[0]} et {HAUTEUR[1]} mm")
    return hauteur


def verifier_penche(textes: list[str]) -> tuple[int, int, int]:
    x, y, z = (entier(t, "Chaque angle") for t in textes)
    for valeur in (x, y, z):
        if not -PENCHE_MAX <= valeur <= PENCHE_MAX:
            raise ErreurValeur(f"Chaque angle doit être compris entre −{PENCHE_MAX} et {PENCHE_MAX}°")
    total = math.sqrt(x * x + y * y + z * z)
    if total > PENCHE_MAX:
        raise ErreurValeur(
            f"Inclinaison totale de {total:.0f}° : le robot ne dépasse pas {PENCHE_MAX}° en tout"
        )
    return x, y, z


def verifier_decale(textes: list[str]) -> tuple[int, int, int]:
    x, y = (entier(t, "Le décalage") for t in textes[:2])
    z = entier(textes[2], "La hauteur")
    for valeur in (x, y):
        if not -DECALE_MAX <= valeur <= DECALE_MAX:
            raise ErreurValeur(f"Le décalage x et y doit être compris entre −{DECALE_MAX} et {DECALE_MAX} mm")
    if not HAUTEUR[0] <= z <= HAUTEUR[1]:
        raise ErreurValeur(f"La hauteur (z) doit être comprise entre {HAUTEUR[0]} et {HAUTEUR[1]} mm")
    return x, y, z


# --- Le robot -----------------------------------------------------------------------------


class Robot:
    def __init__(self, transport: TransportUSB, reglages: Reglages) -> None:
        self.transport = transport
        self.reglages = reglages

    def tension(self) -> float:
        reponse = self.transport.demander(protocole.trame(protocole.DEMANDE_TENSION))
        try:
            return protocole.tension(reponse)
        except protocole.ErreurProtocole as e:
            raise ErreurRobot(f"Réponse du robot incompréhensible ({e})") from e

    def verifier_batterie(self) -> None:
        valeur = self.tension()
        if valeur < self.reglages.seuil_faible:
            volts = f"{valeur:.2f}".replace(".", ",")
            raise ErreurRobot(
                f"Batteries trop faibles ({volts} V) : mouvement refusé. "
                "Les recharger ; « spiderbot couche » reste possible."
            )

    def executer(self, ordre: int, *donnees: int) -> None:
        """Envoie un ordre bloquant et attend la fin du mouvement."""
        reponse = self.transport.demander(protocole.trame(ordre, *donnees))
        if reponse.ordre != protocole.ORDRE_COMMENCE:
            raise ErreurRobot(f"Le robot a refusé l'ordre {ordre} (réponse {reponse.ordre})")
        fin = self.transport.recevoir(FIN_MOUVEMENT)
        if fin is None or fin.ordre != protocole.ORDRE_FINI:
            raise RobotMuet(
                f"Le mouvement ne s'est pas terminé en {FIN_MOUVEMENT:g} s "
                "(robot bloqué ? batteries ?)"
            )

    def reveiller(self) -> None:
        self.executer(protocole.MODE_ACTIF)

    def coucher(self) -> None:
        self.executer(protocole.MODE_REPOS)

    def bouger(self, ordre: int, *donnees: int) -> None:
        """Un mouvement de posture : batterie vérifiée, réveil, puis l'ordre."""
        self.verifier_batterie()
        self.reveiller()
        self.executer(ordre, *donnees)

    def marcher(self, ordre: int, pas: int, apres_chaque_pas: Callable[[int], None] | None = None) -> None:
        """Enchaîne `pas` pas, un par un. Ctrl+C : le pas en cours se termine, puis arrêt.

        Un second Ctrl+C abandonne l'attente du pas en cours (le robot, lui, le finit).
        """
        self.verifier_batterie()
        self.reveiller()
        demande_arret = False

        def sur_ctrl_c(signum: int, frame: FrameType | None) -> None:
            nonlocal demande_arret
            if demande_arret:
                raise KeyboardInterrupt
            demande_arret = True

        precedent = signal.signal(signal.SIGINT, sur_ctrl_c)
        try:
            for fait in range(pas):
                if demande_arret:
                    raise Interrompu(fait, pas)
                self.executer(ordre)
                if apres_chaque_pas:
                    apres_chaque_pas(fait + 1)
        finally:
            signal.signal(signal.SIGINT, precedent)
