"""La commande `spiderbot`."""

import argparse
import sys
from collections.abc import Callable

from . import protocole, reglages
from .robot import MARCHES, ErreurValeur, Interrompu, Robot
from .robot import verifier_decale, verifier_hauteur, verifier_pas, verifier_penche
from .transport import ErreurRobot, TransportUSB, trouver_port_usb


def volts(valeur: float) -> str:
    return f"{valeur:.2f}".replace(".", ",") + " V"


def etat_batterie(tension: float, r: reglages.Reglages) -> str:
    if tension >= r.seuil_ok:
        return "ok"
    if tension >= r.seuil_faible:
        return "à recharger bientôt"
    return "trop faible"


def ouvrir(args: argparse.Namespace, r: reglages.Reglages) -> TransportUSB:
    transport = "wifi" if args.wifi else "usb" if args.usb else r.transport
    if transport == "wifi":
        raise ErreurRobot("Le pilotage par wifi n'est pas encore disponible : utiliser --usb")
    port = args.port or (r.port_usb if r.port_usb != "auto" else trouver_port_usb())
    return TransportUSB(port, r.delai)


def avec_robot(args: argparse.Namespace, r: reglages.Reglages, action: Callable[[Robot], None]) -> None:
    """Ouvre la liaison, attend que le robot soit prêt, puis lance l'action."""
    with ouvrir(args, r) as liaison:
        liaison.attendre_pret()
        action(Robot(liaison, r))


# --- Commandes ----------------------------------------------------------------------------


def cmd_etat(args: argparse.Namespace, r: reglages.Reglages) -> None:
    with ouvrir(args, r) as liaison:
        duree = liaison.attendre_pret()
    print(f"Robot présent sur {liaison.port} (réponse en {duree:.1f} s)".replace(".", ","))


def cmd_batterie(args: argparse.Namespace, r: reglages.Reglages) -> None:
    def action(robot: Robot) -> None:
        valeur = robot.tension()
        print(f"Batterie : {volts(valeur)} ({etat_batterie(valeur, r)})")

    avec_robot(args, r, action)


def cmd_marche(args: argparse.Namespace, r: reglages.Reglages) -> None:
    nom = f"tourne {args.sens}" if args.marche == "tourne" else args.marche
    pas = verifier_pas(args.pas)  # avant d'ouvrir le port : rien n'est envoyé si c'est faux

    def action(robot: Robot) -> None:
        robot.marcher(MARCHES[nom], pas)
        print(f"{nom.capitalize()} : {pas} pas")

    try:
        avec_robot(args, r, action)
    except Interrompu as e:
        print(f"Arrêté après {e.faits} pas sur {e.prevus} (Ctrl+C) : le robot est debout.")
        raise


def cmd_hauteur(args: argparse.Namespace, r: reglages.Reglages) -> None:
    hauteur = verifier_hauteur(args.hauteur)
    avec_robot(args, r, lambda robot: robot.bouger(protocole.HAUTEUR, protocole.signe(hauteur)))
    print(f"Hauteur : {hauteur} mm")


def cmd_penche(args: argparse.Namespace, r: reglages.Reglages) -> None:
    angles = verifier_penche(args.angles)
    donnees = [protocole.signe(a) for a in angles]
    avec_robot(args, r, lambda robot: robot.bouger(protocole.PENCHE_CORPS, *donnees))
    print("Penché : x {} °, y {} °, z {} °".format(*angles))


def cmd_decale(args: argparse.Namespace, r: reglages.Reglages) -> None:
    valeurs = verifier_decale(args.valeurs)
    donnees = [protocole.signe(v) for v in valeurs]
    avec_robot(args, r, lambda robot: robot.bouger(protocole.DECALE_CORPS, *donnees))
    print("Décalé : x {} mm, y {} mm, hauteur {} mm".format(*valeurs))


def cmd_couche(args: argparse.Namespace, r: reglages.Reglages) -> None:
    avec_robot(args, r, lambda robot: robot.coucher())  # permis même batteries faibles
    print("Couché.")


def cmd_reveille(args: argparse.Namespace, r: reglages.Reglages) -> None:
    def action(robot: Robot) -> None:
        robot.verifier_batterie()
        robot.reveiller()

    avec_robot(args, r, action)
    print("Debout.")


# --- Analyse de la ligne de commande ------------------------------------------------------


def analyseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spiderbot", description="Pilote l'araignée robot.")
    liaison = p.add_mutually_exclusive_group()
    liaison.add_argument("--usb", action="store_true", help="passer par le câble USB")
    liaison.add_argument("--wifi", action="store_true", help="passer par le wifi (à venir)")
    p.add_argument("--port", help="port série à utiliser (par défaut : détection automatique)")
    sous = p.add_subparsers(dest="commande", required=True, metavar="commande")

    sous.add_parser("etat", help="dit si le robot répond").set_defaults(fonction=cmd_etat)
    sous.add_parser("batterie", help="tension des batteries").set_defaults(fonction=cmd_batterie)

    for nom, aide in (("avance", "marcher en avant"), ("recule", "marcher en arrière"),
                      ("gauche", "pas de côté vers la gauche"), ("droite", "pas de côté vers la droite")):
        c = sous.add_parser(nom, help=aide)
        c.add_argument("pas", nargs="?", help=f"nombre de pas, de 1 à 20 (1 par défaut)")
        c.set_defaults(fonction=cmd_marche, marche=nom, sens=None)

    c = sous.add_parser("tourne", help="tourner sur place")
    c.add_argument("sens", choices=["gauche", "droite"])
    c.add_argument("pas", nargs="?", help="nombre de pas, de 1 à 20 (1 par défaut)")
    c.set_defaults(fonction=cmd_marche, marche="tourne")

    c = sous.add_parser("hauteur", help="hauteur du corps, en mm (0 à 45)")
    c.add_argument("hauteur")
    c.set_defaults(fonction=cmd_hauteur)

    c = sous.add_parser("penche", help="pencher le corps, en degrés (15° en tout au plus)")
    c.add_argument("angles", nargs=3, metavar=("x", "y", "z"))
    c.set_defaults(fonction=cmd_penche)

    c = sous.add_parser("decale", help="décaler le corps sans marcher : x y en mm (±20), z hauteur 0 à 45")
    c.add_argument("valeurs", nargs=3, metavar=("x", "y", "z"))
    c.set_defaults(fonction=cmd_decale)

    sous.add_parser("couche", help="se coucher (repos)").set_defaults(fonction=cmd_couche)
    sous.add_parser("reveille", help="se mettre debout").set_defaults(fonction=cmd_reveille)
    return p


def main(argv: list[str] | None = None) -> int:
    args = analyseur().parse_args(argv)
    try:
        r = reglages.charger()
        args.fonction(args, r)
    except (reglages.ErreurReglages, ErreurValeur) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except ErreurRobot as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except (Interrompu, KeyboardInterrupt):
        print("Interrompu.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
