"""La commande `spiderbot`."""

import argparse
import sys

from . import protocole, reglages
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


def cmd_etat(args: argparse.Namespace, r: reglages.Reglages) -> None:
    with ouvrir(args, r) as robot:
        duree = robot.attendre_pret()
    print(f"Robot présent sur {robot.port} (réponse en {duree:.1f} s)".replace(".", ","))


def cmd_batterie(args: argparse.Namespace, r: reglages.Reglages) -> None:
    with ouvrir(args, r) as robot:
        robot.attendre_pret()
        reponse = robot.demander(protocole.trame(protocole.DEMANDE_TENSION))
    try:
        valeur = protocole.tension(reponse)
    except protocole.ErreurProtocole as e:
        raise ErreurRobot(f"Réponse du robot incompréhensible ({e})") from e
    print(f"Batterie : {volts(valeur)} ({etat_batterie(valeur, r)})")


def analyseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spiderbot", description="Pilote l'araignée robot.")
    liaison = p.add_mutually_exclusive_group()
    liaison.add_argument("--usb", action="store_true", help="passer par le câble USB")
    liaison.add_argument("--wifi", action="store_true", help="passer par le wifi (à venir)")
    p.add_argument("--port", help="port série à utiliser (par défaut : détection automatique)")
    sous = p.add_subparsers(dest="commande", required=True, metavar="commande")
    sous.add_parser("etat", help="dit si le robot répond").set_defaults(fonction=cmd_etat)
    sous.add_parser("batterie", help="tension des batteries").set_defaults(fonction=cmd_batterie)
    return p


def main(argv: list[str] | None = None) -> int:
    args = analyseur().parse_args(argv)
    try:
        r = reglages.charger()
        args.fonction(args, r)
    except reglages.ErreurReglages as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except ErreurRobot as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
