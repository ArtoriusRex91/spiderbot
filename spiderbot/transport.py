"""Transport des trames vers le robot. Pour l'instant par USB ; le wifi viendra plus tard."""

import time

import serial
from serial.tools import list_ports

from . import protocole

VITESSE_USB = 115_200
# Silence à respecter après l'ouverture du port : la carte redémarre, et son chargeur de
# démarrage reste bloqué pour de bon s'il reçoit un octet trop tôt (mesuré : 0,5 s bloque,
# 1 s suffit). On garde de la marge.
SILENCE_DEMARRAGE = 1.5
# Arduino Mega 2560 d'origine (identifiant USB vendeur:produit)
ID_MEGA = (0x2341, 0x0010)


class ErreurRobot(Exception):
    """Problème de communication avec le robot, avec un message lisible."""


class RobotIntrouvable(ErreurRobot):
    pass


class RobotMuet(ErreurRobot):
    pass


def trouver_port_usb() -> str:
    """Cherche la carte du robot parmi les ports série, par son identifiant USB."""
    for port in list_ports.comports():
        if (port.vid, port.pid) == ID_MEGA:
            return port.device
    raise RobotIntrouvable("Robot introuvable : aucune carte Mega 2560 branchée en USB")


class TransportUSB:
    """Liaison série USB avec le robot.

    Ouvrir le port redémarre la carte (comme l'IDE Arduino). `attendre_pret` se tait le temps
    du redémarrage, puis relance un écho jusqu'à la réponse ou jusqu'au délai.
    """

    silence_demarrage = SILENCE_DEMARRAGE

    def __init__(self, port: str, delai: float = 5.0) -> None:
        self.port = port
        self.delai = delai
        self._serie: serial.Serial | None = None
        self._decodeur = protocole.Decodeur()

    def __enter__(self) -> "TransportUSB":
        self.ouvrir()
        return self

    def __exit__(self, *exc: object) -> None:
        self.fermer()

    def ouvrir(self) -> None:
        try:
            self._serie = serial.Serial(self.port, VITESSE_USB, timeout=0.05)
        except serial.SerialException as e:
            if isinstance(e.__context__, PermissionError) or "Permission denied" in str(e):
                raise ErreurRobot(
                    f"Accès refusé à {self.port} : le compte doit faire partie du groupe "
                    "dialout (sudo usermod -aG dialout $USER, puis se reconnecter)"
                ) from e
            raise RobotIntrouvable(f"Robot introuvable sur {self.port}") from e

    def fermer(self) -> None:
        if self._serie is not None:
            self._serie.close()
            self._serie = None

    def _recevoir(self, fin: float) -> protocole.Reponse | None:
        """Première trame reçue avant l'instant `fin`, sinon None."""
        assert self._serie is not None
        while time.monotonic() < fin:
            for reponse in self._decodeur.ajouter(self._serie.read(64)):
                return reponse
        return None

    def attendre_pret(self) -> float:
        """Attend que le robot réponde à un écho ; renvoie le temps écoulé, en secondes."""
        assert self._serie is not None
        debut = time.monotonic()
        fin = debut + self.delai
        time.sleep(min(self.silence_demarrage, self.delai))
        self._serie.reset_input_buffer()  # bruit éventuel du redémarrage
        while time.monotonic() < fin:
            self._serie.write(protocole.trame(protocole.DEMANDE_ECHO))
            reponse = self._recevoir(min(fin, time.monotonic() + 0.3))
            if reponse is not None and reponse.ordre == protocole.ECHO:
                return time.monotonic() - debut
        raise RobotMuet(
            f"Le robot ne répond pas sur {self.port} (éteint ? occupé à bouger ? "
            "programme d'origine absent ?)"
        )

    def recevoir(self, delai: float) -> protocole.Reponse | None:
        """Prochaine trame reçue dans le délai, sinon None."""
        return self._recevoir(time.monotonic() + delai)

    def demander(self, trame: bytes) -> protocole.Reponse:
        """Envoie une trame et renvoie la première réponse, dans le délai."""
        assert self._serie is not None
        self._serie.write(trame)
        reponse = self._recevoir(time.monotonic() + self.delai)
        if reponse is None:
            raise RobotMuet(f"Le robot ne répond plus sur {self.port}")
        return reponse
