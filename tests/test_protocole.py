import pytest

from spiderbot import protocole as p


def test_trame_encadre_ordre_et_donnees():
    assert p.trame(p.DEMANDE_TENSION) == bytes([128, 10, 129])
    assert p.trame(110, 64, 70, 60) == bytes([128, 110, 64, 70, 60, 129])


@pytest.mark.parametrize("valeur", [-1, 128, 200])
def test_trame_refuse_les_valeurs_hors_limites(valeur):
    with pytest.raises(p.ErreurProtocole):
        p.trame(110, valeur)


def test_decodeur_reconstitue_une_trame_coupee_en_morceaux():
    d = p.Decodeur()
    assert list(d.ajouter(bytes([128, 11]))) == []
    assert list(d.ajouter(bytes([6, 16, 129]))) == [p.Reponse(11, (6, 16))]


def test_decodeur_ignore_le_bruit_hors_trame():
    d = p.Decodeur()
    flux = b"\x00\x05demarrage" + bytes([128, 1, 129]) + b"\x7f"
    assert list(d.ajouter(flux)) == [p.Reponse(1, ())]


def test_decodeur_abandonne_une_trame_interrompue_par_un_nouveau_debut():
    d = p.Decodeur()
    assert list(d.ajouter(bytes([128, 11, 6, 128, 1, 129]))) == [p.Reponse(1, ())]


def test_decodeur_plusieurs_trames_dun_coup():
    d = p.Decodeur()
    flux = bytes([128, 21, 129, 128, 23, 129])
    assert list(d.ajouter(flux)) == [p.Reponse(21, ()), p.Reponse(23, ())]


def test_decodage_de_la_tension():
    # 7,84 V = 784 centièmes = 6 × 128 + 16
    assert p.tension(p.Reponse(p.TENSION, (6, 16))) == pytest.approx(7.84)


@pytest.mark.parametrize("reponse", [p.Reponse(p.TENSION, (5,)), p.Reponse(p.ECHO, ())])
def test_tension_mal_formee_refusee(reponse):
    with pytest.raises(p.ErreurProtocole):
        p.tension(reponse)
