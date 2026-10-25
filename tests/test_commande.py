import time

import pytest

from spiderbot import commande, reglages
from robot_simule import RobotSimule


@pytest.fixture(autouse=True)
def reglages_isoles(tmp_path, monkeypatch):
    """Aucun test ne lit les réglages réels de la machine."""
    chemin = tmp_path / "config.toml"
    monkeypatch.setenv("SPIDERBOT_CONFIG", str(chemin))
    return chemin


@pytest.fixture(autouse=True)
def demarrage_rapide(monkeypatch):
    """Le simulateur se bloque 0,1 s au lieu d'une seconde : on se tait 0,2 s pour aller vite."""
    monkeypatch.setattr("spiderbot.transport.TransportUSB.silence_demarrage", 0.2)


def lancer(capsys, *args):
    code = commande.main(list(args))
    sortie = capsys.readouterr()
    return code, sortie.out, sortie.err


def test_etat_robot_present(capsys):
    with RobotSimule() as robot:
        code, out, _ = lancer(capsys, "--port", robot.port, "etat")
    assert code == 0
    assert out.startswith(f"Robot présent sur {robot.port}")


def test_silence_au_demarrage_comme_la_vraie_carte(capsys, monkeypatch):
    """Valeurs réelles : chargeur bloqué par un octet avant 1 s, silence de 1,5 s."""
    monkeypatch.setattr("spiderbot.transport.TransportUSB.silence_demarrage", 1.5)
    with RobotSimule(chargeur=1.0) as robot:
        code, out, _ = lancer(capsys, "--port", robot.port, "batterie")
        assert not robot.bloque
    assert code == 0, out


def test_sans_silence_le_chargeur_se_bloque(capsys, monkeypatch):
    """Garde-fou : le simulateur reproduit bien le piège de la vraie carte."""
    monkeypatch.setattr("spiderbot.transport.TransportUSB.silence_demarrage", 0.0)
    with RobotSimule(chargeur=1.0) as robot:
        code, _, err = lancer(capsys, "--port", robot.port, "etat")
        assert robot.bloque
    assert code == 1 and "ne répond pas" in err


def test_etat_attend_la_fin_du_redemarrage(capsys):
    with RobotSimule(demarrage=1.0) as robot:
        code, out, _ = lancer(capsys, "--port", robot.port, "etat")
    assert code == 0, out


def test_batterie_affiche_tension_et_etat(capsys):
    with RobotSimule(tension=7.84) as robot:
        code, out, _ = lancer(capsys, "--usb", "--port", robot.port, "batterie")
    assert code == 0
    assert out == "Batterie : 7,84 V (ok)\n"


@pytest.mark.parametrize(
    "tension, etat",
    [(8.40, "ok"), (7.20, "ok"), (7.00, "à recharger bientôt"), (6.80, "à recharger bientôt"), (6.50, "trop faible"), (0.0, "trop faible")],
)
def test_batterie_seuils(capsys, tension, etat):
    with RobotSimule(tension=tension) as robot:
        code, out, _ = lancer(capsys, "--port", robot.port, "batterie")
    assert code == 0
    assert out.endswith(f"({etat})\n")


def test_seuils_lus_dans_les_reglages(capsys, reglages_isoles):
    reglages_isoles.write_text("[batterie]\nseuil_ok = 8.0\nseuil_faible = 7.9\n")
    with RobotSimule(tension=7.84) as robot:
        _, out, _ = lancer(capsys, "--port", robot.port, "batterie")
    assert out.endswith("(trop faible)\n")


def test_robot_muet_rend_la_main_en_moins_de_5_secondes(capsys):
    with RobotSimule(muet=True) as robot:
        debut = time.monotonic()
        code, _, err = lancer(capsys, "--port", robot.port, "batterie")
        duree = time.monotonic() - debut
    assert code == 1
    assert "ne répond pas" in err
    assert duree < 5.5  # délai par défaut de 5 s, plus la fermeture du port


def test_delai_plus_court_dans_les_reglages(capsys, reglages_isoles):
    reglages_isoles.write_text("[robot]\ndelai = 0.5\n")
    with RobotSimule(muet=True) as robot:
        debut = time.monotonic()
        code, _, _ = lancer(capsys, "--port", robot.port, "etat")
    assert code == 1
    assert time.monotonic() - debut < 1.5


def test_port_inexistant(capsys):
    code, _, err = lancer(capsys, "--port", "/dev/ttyACM-absent", "etat")
    assert code == 1
    assert "Robot introuvable sur /dev/ttyACM-absent" in err


def test_aucune_carte_branchee(capsys, monkeypatch):
    monkeypatch.setattr("spiderbot.transport.list_ports.comports", lambda: [])
    code, _, err = lancer(capsys, "etat")
    assert code == 1
    assert "aucune carte Mega 2560" in err


def test_reponse_de_tension_mal_formee(capsys):
    with RobotSimule(tension_malformee=True) as robot:
        code, _, err = lancer(capsys, "--port", robot.port, "batterie")
    assert code == 1
    assert "incompréhensible" in err


def test_bruit_au_demarrage_ignore(capsys):
    with RobotSimule(bruit_au_demarrage=b"\x00\xffdemarrage\r\n") as robot:
        code, out, _ = lancer(capsys, "--port", robot.port, "batterie")
    assert code == 0
    assert "7,84 V" in out


def test_wifi_pas_encore_disponible(capsys):
    code, _, err = lancer(capsys, "--wifi", "etat")
    assert code == 1
    assert "pas encore disponible" in err


@pytest.mark.parametrize(
    "contenu, message",
    [
        ("[robot]\ndelai = 9\n", "delai"),
        ("[robot]\ntransport = \"bluetooth\"\n", "transport"),
        ("[robot]\nvitesse = 3\n", "inconnu"),
        ("[batterie]\nseuil_ok = 6\nseuil_faible = 7\n", "seuil_faible"),
        ("pas du toml", "illisibles"),
    ],
)
def test_reglages_invalides(capsys, reglages_isoles, contenu, message):
    reglages_isoles.write_text(contenu)
    code, _, err = lancer(capsys, "--port", "/dev/null", "etat")
    assert code == 2
    assert message in err


def test_exemple_de_reglages_valide(monkeypatch):
    from pathlib import Path

    exemple = Path(__file__).parent.parent / "config.exemple.toml"
    assert reglages.charger(exemple) == reglages.Reglages()
