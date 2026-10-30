import pytest

from app.main import host_de_escucha, puerto_de_escucha


def test_produccion_escucha_en_todas_las_interfaces() -> None:
    assert host_de_escucha() == "0.0.0.0"


def test_puerto_usa_port_o_el_predeterminado_local() -> None:
    assert puerto_de_escucha({}) == 8000
    assert puerto_de_escucha({"PORT": "10000"}) == 10000
    assert puerto_de_escucha({"PORT": "  "}) == 8000


def test_puerto_invalido_se_rechaza() -> None:
    with pytest.raises(ValueError, match="PORT"):
        puerto_de_escucha({"PORT": "ochenta"})
    with pytest.raises(ValueError, match="PORT"):
        puerto_de_escucha({"PORT": "0"})
