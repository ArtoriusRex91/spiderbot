"""Réglages locaux, lus dans ~/.config/spiderbot/config.toml (jamais dans le dépôt).

Le fichier est facultatif : sans lui, les valeurs par défaut s'appliquent. Modèle commenté :
config.exemple.toml à la racine du dépôt.
"""

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

DELAI_MAX = 5.0


class ErreurReglages(Exception):
    pass


@dataclass(frozen=True)
class Reglages:
    transport: str = "usb"  # « usb » ; « wifi » viendra plus tard
    port_usb: str = "auto"  # « auto » : la carte est cherchée par son identifiant USB
    delai: float = DELAI_MAX  # attente maximale d'une réponse, en secondes
    seuil_ok: float = 7.2  # au-dessus : « ok »
    seuil_faible: float = 6.8  # en dessous : « trop faible » ; entre les deux : « à recharger bientôt »


def chemin_par_defaut() -> Path:
    if "SPIDERBOT_CONFIG" in os.environ:
        return Path(os.environ["SPIDERBOT_CONFIG"])
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "spiderbot" / "config.toml"


def charger(chemin: Path | None = None) -> Reglages:
    chemin = chemin or chemin_par_defaut()
    if not chemin.exists():
        return Reglages()
    try:
        donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ErreurReglages(f"Réglages illisibles dans {chemin} : {e}") from e

    plat = {**donnees.get("robot", {}), **donnees.get("batterie", {})}
    connus = {f.name: f.type for f in fields(Reglages)}
    inconnus = set(plat) - set(connus)
    if inconnus:
        raise ErreurReglages(f"Réglage inconnu dans {chemin} : {', '.join(sorted(inconnus))}")
    try:
        reglages = Reglages(**{
            cle: float(val) if connus[cle] is float else str(val) for cle, val in plat.items()
        })
    except (TypeError, ValueError) as e:
        raise ErreurReglages(f"Réglage invalide dans {chemin} : {e}") from e

    if reglages.transport not in ("usb", "wifi"):
        raise ErreurReglages(f"transport doit valoir « usb » ou « wifi », pas « {reglages.transport} »")
    if not 0 < reglages.delai <= DELAI_MAX:
        raise ErreurReglages(f"delai doit être compris entre 0 et {DELAI_MAX:g} secondes")
    if reglages.seuil_faible >= reglages.seuil_ok:
        raise ErreurReglages("seuil_faible doit être inférieur à seuil_ok")
    return reglages
