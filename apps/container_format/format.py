import struct
from dataclasses import dataclass

from .errors import ContainerFormatError, ContainerLimitError
from .spec import (
    CURRENT_VERSION,
    HEADER_FORMAT,
    HEADER_SIZE,
    MAGIC,
    MAX_CARRIER_BYTES,
    MAX_CONTAINER_BYTES,
)


@dataclass(frozen=True)
class ContainerHeader:
    version: int
    flags: int
    carrier_length: int
    ciphertext_length: int
    salt: bytes
    nonce: bytes


@dataclass(frozen=True)
class PixelVaultContainer:
    carrier: bytes
    header: ContainerHeader
    ciphertext: bytes


def _validate_lengths(carrier_length: int, ciphertext_length: int) -> None:
    if carrier_length < 0 or ciphertext_length <= 0:
        raise ContainerFormatError("invalid container lengths")
    if carrier_length > MAX_CARRIER_BYTES:
        raise ContainerLimitError("carrier exceeds the configured size limit")
    if HEADER_SIZE + carrier_length + ciphertext_length > MAX_CONTAINER_BYTES:
        raise ContainerLimitError("container exceeds the configured size limit")


def serialize(container: PixelVaultContainer) -> bytes:
    header = container.header
    if header.version != CURRENT_VERSION:
        raise ContainerFormatError("unsupported container version")
    if len(header.salt) != 16 or len(header.nonce) != 12:
        raise ContainerFormatError("invalid cryptographic parameter length")
    if header.carrier_length != len(container.carrier):
        raise ContainerFormatError("carrier length does not match carrier bytes")
    if header.ciphertext_length != len(container.ciphertext):
        raise ContainerFormatError("ciphertext length does not match ciphertext bytes")
    _validate_lengths(header.carrier_length, header.ciphertext_length)
    packed_header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        header.version,
        header.flags,
        HEADER_SIZE,
        header.carrier_length,
        header.ciphertext_length,
        header.salt,
        header.nonce,
    )
    return packed_header + container.carrier + container.ciphertext


def deserialize(blob: bytes) -> PixelVaultContainer:
    if len(blob) < HEADER_SIZE:
        raise ContainerFormatError("container is shorter than its header")
    magic, version, flags, header_length, carrier_length, ciphertext_length, salt, nonce = struct.unpack(
        HEADER_FORMAT, blob[:HEADER_SIZE]
    )
    if magic != MAGIC:
        raise ContainerFormatError("invalid PixelVault magic")
    if version != CURRENT_VERSION:
        raise ContainerFormatError("unsupported container version")
    if header_length != HEADER_SIZE:
        raise ContainerFormatError("unsupported header length")
    _validate_lengths(carrier_length, ciphertext_length)
    expected_length = HEADER_SIZE + carrier_length + ciphertext_length
    if len(blob) != expected_length:
        raise ContainerFormatError("container length does not match its header")
    carrier_end = HEADER_SIZE + carrier_length
    return PixelVaultContainer(
        carrier=blob[HEADER_SIZE:carrier_end],
        header=ContainerHeader(
            version=version,
            flags=flags,
            carrier_length=carrier_length,
            ciphertext_length=ciphertext_length,
            salt=salt,
            nonce=nonce,
        ),
        ciphertext=blob[carrier_end:],
    )
