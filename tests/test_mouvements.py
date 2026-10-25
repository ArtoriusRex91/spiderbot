import os
import signal
import threading
import time

import pytest

from spiderbot import commande, protocole as p
from robot_simule import RobotSimule


@pytest.fixture(autouse=True)
def isolement(tmp_path, monkeypatch):
    monkeypatch.setenv("SPIDERBOT_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr("spiderbot.transport.TransportUSB.silence_demarrage", 0.2)


def lancer(capsys, robot, *args):
    code = commande.main(["--port", robot.port, *args])
    sortie = capsys.readouterr()
    return code, sortie.out, sortie.err


def mouvements(robot):
    return [(m.ordre, m.donnees) for m in robot.mouvements]


# --- Marche -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args, ordre",
    [
        (["avance"], p.AVANCE),
        (["recule"], p.RECULE),
        (["gauche"], p.GAUCHE),
        (["droite"], p.DROITE),
        (["tourne", "gauche"], p.TOURNE_GAUCHE),
        (["tourne", "droite"], p.TOURNE_DROITE),
    ],
)
def test_chaque_marche_envoie_le_bon_ordre(capsys, args, ordre):
    with RobotSimule() as robot:
        code, out, _ = lancer(capsys, robot, *args)
    assert code == 0, out
    # vérification de la batterie, réveil, puis un pas
    assert robot.ordres() == [p.DEMANDE_ECHO, p.DEMANDE_TENSION, p.MODE_ACTIF, ordre]
    assert mouvements(robot) == [(p.MODE_ACTIF, ()), (ordre, ())]


def test_avance_5_envoie_5_pas_chacun_apres_la_fin_du_precedent(capsys):
    with RobotSimule(duree_mouvement=0.1) as robot:
        code, out, _ = lancer(capsys, robot, "avance", "5")
    assert code == 0
    assert out == "Avance : 5 pas\n"
    assert [o for o, _ in mouvements(robot)] == [p.MODE_ACTIF] + [p.AVANCE] * 5
    assert robot.ignores == []  # aucun ordre envoyé pendant un mouvement


def test_reveil_avant_le_premier_mouvement(capsys):
    with RobotSimule() as robot:
        lancer(capsys, robot, "hauteur", "10")
        assert robot.mode == "actif"
    assert mouvements(robot)[0] == (p.MODE_ACTIF, ())


# --- Postures -----------------------------------------------------------------------------


def test_hauteur(capsys):
    with RobotSimule() as robot:
        code, out, _ = lancer(capsys, robot, "hauteur", "30")
    assert code == 0 and out == "Hauteur : 30 mm\n"
    assert mouvements(robot)[-1] == (p.HAUTEUR, (64 + 30,))


def test_penche_valeurs_signees(capsys):
    with RobotSimule() as robot:
        code, _, _ = lancer(capsys, robot, "penche", "10", "-5", "0")
    assert code == 0
    assert mouvements(robot)[-1] == (p.PENCHE_CORPS, (74, 59, 64))


def test_decale(capsys):
    with RobotSimule() as robot:
        code, _, _ = lancer(capsys, robot, "decale", "-20", "15", "30")
    assert code == 0
    assert mouvements(robot)[-1] == (p.DECALE_CORPS, (44, 79, 94))


def test_couche_et_reveille(capsys):
    with RobotSimule() as robot:
        assert lancer(capsys, robot, "reveille")[0] == 0
        assert robot.mode == "actif"
        assert lancer(capsys, robot, "couche")[0] == 0
        assert robot.mode == "repos"


# --- Valeurs refusées avant tout envoi ----------------------------------------------------


@pytest.mark.parametrize(
    "args, message",
    [
        (["avance", "0"], "entre 1 et 20"),
        (["avance", "21"], "entre 1 et 20"),
        (["avance", "deux"], "nombre entier"),
        (["tourne", "gauche", "50"], "entre 1 et 20"),
        (["hauteur", "46"], "entre 0 et 45"),
        (["hauteur", "-1"], "entre 0 et 45"),
        (["penche", "16", "0", "0"], "entre −15 et 15"),
        (["penche", "15", "15", "0"], "15° en tout"),
        (["decale", "21", "0", "0"], "entre −20 et 20"),
        (["decale", "0", "0", "50"], "hauteur (z)"),
    ],
)
def test_valeurs_hors_limites_refusees_sans_rien_envoyer(capsys, args, message):
    with RobotSimule() as robot:
        code, _, err = lancer(capsys, robot, *args)
        time.sleep(0.1)
        assert robot.recus == []  # le port n'a même pas été ouvert pour parler
    assert code == 2
    assert message in err


# --- Batterie -----------------------------------------------------------------------------


def test_batterie_trop_faible_refuse_les_mouvements(capsys):
    with RobotSimule(tension=6.5) as robot:
        code, _, err = lancer(capsys, robot, "avance")
        assert p.AVANCE not in robot.ordres() and p.MODE_ACTIF not in robot.ordres()
    assert code == 1
    assert "trop faibles (6,50 V)" in err


@pytest.mark.parametrize("args", [["couche"], ["batterie"], ["etat"]])
def test_batterie_trop_faible_couche_batterie_etat_permis(capsys, args):
    with RobotSimule(tension=6.5) as robot:
        code, out, _ = lancer(capsys, robot, *args)
    assert code == 0, out


# --- Arrêt --------------------------------------------------------------------------------


def ctrl_c_apres(delai):
    threading.Timer(delai, lambda: os.kill(os.getpid(), signal.SIGINT)).start()


def test_ctrl_c_finit_le_pas_en_cours_puis_s_arrete(capsys):
    with RobotSimule(duree_mouvement=0.3) as robot:
        # silence 0,2 + écho + tension + réveil 0,3 : Ctrl+C pendant le 1er ou le 2e pas
        ctrl_c_apres(1.0)
        code, out, _ = lancer(capsys, robot, "avance", "5")
        time.sleep(0.4)
        faits = [o for o, _ in mouvements(robot)].count(p.AVANCE)
    assert code == 130
    assert 1 <= faits < 5
    assert f"Arrêté après {faits} pas sur 5" in out
    assert robot.ignores == []  # le pas en cours a fini avant tout autre envoi


def test_mouvement_qui_ne_finit_pas(capsys, monkeypatch):
    monkeypatch.setattr("spiderbot.robot.FIN_MOUVEMENT", 0.5)
    with RobotSimule(mouvement_sans_fin=True) as robot:
        code, _, err = lancer(capsys, robot, "avance")
    assert code == 1
    assert "ne s'est pas terminé" in err
