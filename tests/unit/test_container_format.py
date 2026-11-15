import pytest

from apps.container_format.errors import ContainerFormatError
from apps.container_format.format import deserialize, serialize
from apps.encoding.packaging import InputFile, create_container, decrypt_container
from apps.crypto.service import generate_passcode


def test_container_round_trip_preserves_carrier_and_files():
    carrier = b"fake-png-carrier"
    passcode = generate_passcode()
    blob = serialize(
        create_container(
            carrier,
            [InputFile("notes/readme.txt", b"hello", "text/plain"), InputFile("photo.jpg", b"jpeg")],
            passcode,
        )
    )

    parsed = deserialize(blob)
    recovered = decrypt_container(parsed, passcode)

    assert parsed.carrier == carrier
    assert [(item.name, item.content) for item in recovered] == [
        ("notes/readme.txt", b"hello"),
        ("photo.jpg", b"jpeg"),
    ]


def test_container_rejects_tampering():
    passcode = generate_passcode()
    blob = bytearray(serialize(create_container(b"carrier", [InputFile("a.txt", b"a")], passcode)))
    blob[-1] ^= 1
    parsed = deserialize(bytes(blob))
    with pytest.raises(Exception):
        decrypt_container(parsed, passcode)


def test_container_rejects_path_traversal_name():
    with pytest.raises(ContainerFormatError):
        create_container(b"carrier", [InputFile("../secret.txt", b"secret")], generate_passcode())


def test_recovery_secret_is_required_when_configured():
    passcode = generate_passcode()
    container = create_container(b"carrier", [InputFile("secret.txt", b"secret")], passcode, "strong-secret")
    with pytest.raises(Exception):
        decrypt_container(container, passcode)
    assert decrypt_container(container, passcode, "strong-secret")[0].content == b"secret"
