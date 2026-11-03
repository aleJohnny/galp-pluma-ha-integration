"""Protocolo BLE da garrafa Galp Pluma (deduzido por engenharia inversa).

Este módulo é puro Python: não depende do Home Assistant nem do bleak, para
poder ser testado isoladamente. Ver PROTOCOL.md para o que é conhecido e o que
ainda é hipótese.
"""

from __future__ import annotations

from dataclasses import dataclass

# Serviço personalizado d973f2e0-... ; a característica de comandos/respostas
# é a d973f2e1-... (escrita + notificação). A d973f2e3-... existe mas nunca foi
# vista a ser usada pela app: NÃO escrever nela.
SERVICE_UUID = "d973f2e0-b19e-11e2-9e96-0800200c9a66"
CHAR_UUID = "d973f2e1-b19e-11e2-9e96-0800200c9a66"

# 4 bytes presentes em todos os comandos capturados. Testado em duas garrafas
# (uma pareada com a app, outra nunca pareada) e em várias sessões.
DEFAULT_KEY = bytes.fromhex("6ae8eca5")

CHECKSUM_SEED = 0xAA

CMD_HELLO = 0x55  # a garrafa não responde a este comando
CMD_STATUS = 0x03  # a garrafa responde com uma notificação de 11 bytes

COMMAND_LENGTH = 6
RESPONSE_LENGTH = 11


class PlumaError(Exception):
    """Erro genérico da integração Pluma."""


class PlumaProtocolError(PlumaError):
    """Frame recebida inválida ou inesperada."""


class PlumaConnectionError(PlumaError):
    """Não foi possível ligar à garrafa ou obter resposta."""


@dataclass(frozen=True)
class PlumaReading:
    """Resultado de uma leitura de estado."""

    level: int  # byte 9: nível em %; perto do da app (±3) mas nem sempre igual
    temperature: int  # byte 8: °C com sinal; igual ao da app em 4 de 4 leituras
    byte7: int  # significado desconhecido; varia por garrafa e ±1 com o tempo
    raw: str  # frame completa em hexadecimal, para diagnóstico


def checksum(data: bytes) -> int:
    """Soma dos bytes mais a semente, truncada a um byte."""
    return (sum(data) + CHECKSUM_SEED) & 0xFF


def build_command(cmd: int, key: bytes = DEFAULT_KEY) -> bytes:
    """Constrói um comando de 6 bytes: cmd + chave(4) + checksum."""
    if len(key) != 4:
        raise ValueError("a chave tem de ter 4 bytes")
    body = bytes([cmd]) + key
    return body + bytes([checksum(body)])


def parse_status(frame: bytes) -> PlumaReading:
    """Interpreta a notificação de 11 bytes devolvida pelo comando de estado."""
    if len(frame) != RESPONSE_LENGTH:
        raise PlumaProtocolError(f"tamanho inesperado: {len(frame)} bytes")
    if checksum(frame[:-1]) != frame[-1]:
        raise PlumaProtocolError("checksum inválido")
    if frame[0] != CMD_STATUS:
        raise PlumaProtocolError(f"comando inesperado: 0x{frame[0]:02x}")
    level = frame[9]
    if level > 100:
        raise PlumaProtocolError(f"nível fora do intervalo: {level}")
    return PlumaReading(
        level=level,
        # Com sinal, para garrafas no exterior no inverno.
        temperature=int.from_bytes(frame[8:9], "big", signed=True),
        byte7=frame[7],
        raw=frame.hex(),
    )
