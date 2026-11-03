"""Testes do protocolo com as frames reais capturadas das garrafas."""

import pytest

from galp_pluma import protocol


def test_commands_match_capture():
    assert protocol.build_command(protocol.CMD_HELLO).hex() == "556ae8eca5e2"
    assert protocol.build_command(protocol.CMD_STATUS).hex() == "036ae8eca590"


@pytest.mark.parametrize(
    ("frame", "level", "temperature", "byte7"),
    [
        # Garrafa A (butano), captura HCI da app (app: 89 %)
        ("0301000000000070175a8f", 90, 23, 112),
        ("030100000000007017598e", 89, 23, 112),
        # Garrafa A, script (app: 88 %, 22 °C)
        ("030100000000007116588d", 88, 22, 113),
        # Garrafa A, script (app: 88 %, 16 °C)
        ("0301000000000071105a89", 90, 16, 113),
        # Garrafa B (propano), script
        ("03010000000000821461a5", 97, 20, 130),
        # Garrafa B, script (app: 100 %, 14 °C)
        ("03010000000000830e61a0", 97, 14, 131),
        # Garrafa C (propano, vazia), script (app: 0 %, 18 °C)
        ("030100000000007a12003a", 0, 18, 122),
    ],
)
def test_parse_real_frames(frame, level, temperature, byte7):
    reading = protocol.parse_status(bytes.fromhex(frame))
    assert reading.level == level
    assert reading.temperature == temperature
    assert reading.byte7 == byte7
    assert reading.raw == frame


def test_negative_temperature_is_signed():
    # Frame sintética (não vista numa garrafa): 0xFB = -5 °C
    body = bytes.fromhex("0301000000000070fb58")
    frame = body + bytes([protocol.checksum(body)])
    assert protocol.parse_status(frame).temperature == -5


def test_bad_checksum():
    with pytest.raises(protocol.PlumaProtocolError, match="checksum"):
        protocol.parse_status(bytes.fromhex("0301000000000070175a00"))


def test_bad_length():
    with pytest.raises(protocol.PlumaProtocolError, match="tamanho"):
        protocol.parse_status(bytes.fromhex("030100"))


def test_unexpected_command():
    body = bytes.fromhex("5501000000000070175a")
    frame = body + bytes([protocol.checksum(body)])
    with pytest.raises(protocol.PlumaProtocolError, match="comando"):
        protocol.parse_status(frame)


def test_level_out_of_range():
    body = bytes.fromhex("03010000000000701765")  # 0x65 = 101
    frame = body + bytes([protocol.checksum(body)])
    with pytest.raises(protocol.PlumaProtocolError, match="intervalo"):
        protocol.parse_status(frame)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Pluma--23005677074", True),
        ("PLUMA--23005677074", True),
        ("pluma--1", True),
        ("Truma", False),
        ("", False),
        (None, False),
    ],
)
def test_is_pluma_name(name, expected):
    from galp_pluma.const import is_pluma_name

    assert is_pluma_name(name) is expected


def test_key_length():
    with pytest.raises(ValueError):
        protocol.build_command(protocol.CMD_STATUS, key=b"\x00\x01")
