"""Robot simulé : parle le protocole Freenove sur un faux port série (pseudo-terminal).

Le code testé ouvre `robot.port` exactement comme un vrai /dev/ttyACM*, ce qui fait passer
les tests par le vrai transport série. Comme le vrai robot :
- son chargeur se bloque s'il reçoit un octet trop tôt après l'ouverture ;
- un ordre de mouvement répond « commencé », dure un moment, puis répond « fini » ;
- pendant un mouvement, tout ordre reçu est ignoré, sans réponse.
"""

import os
import pty
import select
import threading
import time
import tty

from spiderbot import protocole


class RobotSimule:
    def __init__(
        self,
        tension: float = 7.84,
        muet: bool = False,
        demarrage: float = 0.0,
        tension_malformee: bool = False,
        bruit_au_demarrage: bytes = b"",
        chargeur: float = 0.1,
        duree_mouvement: float = 0.15,
        mouvement_sans_fin: bool = False,
    ) -> None:
        self.tension = tension
        self.muet = muet  # ne répond jamais (programme absent, carte plantée)
        self.demarrage = demarrage  # secondes de silence après l'ouverture, comme après un reset
        self.tension_malformee = tension_malformee
        self.bruit_au_demarrage = bruit_au_demarrage
        # Comme le chargeur de la Mega : un octet reçu dans les `chargeur` premières secondes
        # le bloque, et la carte ne répond plus jamais.
        self.chargeur = chargeur
        self.bloque = False
        self.duree_mouvement = duree_mouvement
        self.mouvement_sans_fin = mouvement_sans_fin  # « commencé », puis plus rien
        self.mode = "repos"
        self.recus: list[protocole.Reponse] = []  # ordres traités
        self.ignores: list[protocole.Reponse] = []  # ordres reçus pendant un mouvement
        self.mouvements: list[protocole.Reponse] = []  # ordres bloquants terminés, dans l'ordre
        self._arret = threading.Event()

    def __enter__(self) -> "RobotSimule":
        self._maitre, esclave = pty.openpty()
        tty.setraw(esclave)
        self.port = os.ttyname(esclave)
        self._esclave = esclave
        self._fil = threading.Thread(target=self._boucle, daemon=True)
        self._fil.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._arret.set()
        self._fil.join(timeout=2)
        os.close(self._maitre)
        os.close(self._esclave)

    def ordres(self) -> list[int]:
        """Les ordres traités, dans l'ordre de réception."""
        return [r.ordre for r in self.recus]

    def _repondre(self, demande: protocole.Reponse) -> bytes | None:
        if demande.ordre == protocole.DEMANDE_ECHO:
            return protocole.trame(protocole.ECHO)
        if demande.ordre == protocole.DEMANDE_TENSION:
            if self.tension_malformee:
                return protocole.trame(protocole.TENSION, 5)
            centiemes = int(self.tension * 100)
            return protocole.trame(protocole.TENSION, centiemes // 128, centiemes % 128)
        return None

    def _boucle(self) -> None:
        decodeur = protocole.Decodeur()
        debut = time.monotonic()
        bruit_envoye = False
        en_cours: protocole.Reponse | None = None
        fin_mouvement = 0.0
        while not self._arret.is_set():
            if en_cours and not self.mouvement_sans_fin and time.monotonic() >= fin_mouvement:
                if en_cours.ordre == protocole.MODE_ACTIF:
                    self.mode = "actif"
                elif en_cours.ordre == protocole.MODE_REPOS:
                    self.mode = "repos"
                self.mouvements.append(en_cours)
                en_cours = None
                os.write(self._maitre, protocole.trame(protocole.ORDRE_FINI))
            pret, _, _ = select.select([self._maitre], [], [], 0.02)
            if not pret:
                continue
            try:
                octets = os.read(self._maitre, 256)
            except OSError:
                return
            if time.monotonic() - debut < self.chargeur:
                self.bloque = True
            if self.muet or self.bloque or time.monotonic() - debut < self.demarrage:
                continue  # comme une carte en train de redémarrer : tout est perdu
            if not bruit_envoye:
                os.write(self._maitre, self.bruit_au_demarrage)
                bruit_envoye = True
            for demande in decodeur.ajouter(octets):
                if en_cours:
                    self.ignores.append(demande)
                    continue
                self.recus.append(demande)
                if demande.ordre >= 64:  # ordre bloquant
                    en_cours = demande
                    fin_mouvement = time.monotonic() + self.duree_mouvement
                    os.write(self._maitre, protocole.trame(protocole.ORDRE_COMMENCE))
                    continue
                reponse = self._repondre(demande)
                if reponse:
                    os.write(self._maitre, reponse)
