"""Concrete cryptographic adapters for the RQ5 matched implementation.

The module uses the official NTRU+768 reference implementation (pinned under
``third_party/ntruplus``), AES-256-GCM, Ed25519, 3072-bit Paillier/RSA, and a
3072-bit DSA-group Pedersen/ElGamal adapter.  Setup keys are long-lived and are
generated outside the per-task timing region; task operations are all real.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from Crypto.PublicKey import DSA
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from phe import paillier


ROOT = Path(__file__).resolve().parents[1]
NTRUPLUS_LIB = ROOT / "native" / "libntruplus768.so"
PAILLIER_BITS = 3072
RSA_BITS = 3072


def h256(*parts: bytes) -> bytes:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(struct.pack(">I", len(part)))
        digest.update(part)
    return digest.digest()


def fixed_int(value: int, width: int) -> bytes:
    return int(value).to_bytes(width, "big", signed=False)


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    if not leaves:
        return h256(b"EMPTY")
    level = [h256(b"LEAF", item) for item in leaves]
    while len(level) > 1:
        if len(level) & 1:
            level.append(level[-1])
        level = [h256(b"NODE", level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


class NTRUPlus768:
    """ctypes wrapper around the authors' official NTRU+768 C reference code."""

    PUBLIC_KEY_BYTES = 1152
    SECRET_KEY_BYTES = 2336
    CIPHERTEXT_BYTES = 1152
    SHARED_SECRET_BYTES = 32

    def __init__(self, library: Path = NTRUPLUS_LIB):
        self.lib = ctypes.CDLL(str(library))
        u8p = ctypes.POINTER(ctypes.c_ubyte)
        self.lib.crypto_kem_keypair.argtypes = [u8p, u8p]
        self.lib.crypto_kem_keypair.restype = ctypes.c_int
        self.lib.crypto_kem_enc.argtypes = [u8p, u8p, u8p]
        self.lib.crypto_kem_enc.restype = ctypes.c_int
        self.lib.crypto_kem_dec.argtypes = [u8p, u8p, u8p]
        self.lib.crypto_kem_dec.restype = ctypes.c_int

    @staticmethod
    def _array(data: bytes | None, length: int):
        arr = (ctypes.c_ubyte * length)()
        if data is not None:
            if len(data) != length:
                raise ValueError(f"expected {length} bytes, got {len(data)}")
            ctypes.memmove(arr, data, length)
        return arr

    def keypair(self) -> tuple[bytes, bytes]:
        pk = self._array(None, self.PUBLIC_KEY_BYTES)
        sk = self._array(None, self.SECRET_KEY_BYTES)
        if self.lib.crypto_kem_keypair(pk, sk) != 0:
            raise RuntimeError("NTRU+ keypair failed")
        return bytes(pk), bytes(sk)

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        pk = self._array(public_key, self.PUBLIC_KEY_BYTES)
        ct = self._array(None, self.CIPHERTEXT_BYTES)
        ss = self._array(None, self.SHARED_SECRET_BYTES)
        if self.lib.crypto_kem_enc(ct, ss, pk) != 0:
            raise RuntimeError("NTRU+ encapsulation failed")
        return bytes(ct), bytes(ss)

    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        sk = self._array(secret_key, self.SECRET_KEY_BYTES)
        ct = self._array(ciphertext, self.CIPHERTEXT_BYTES)
        ss = self._array(None, self.SHARED_SECRET_BYTES)
        if self.lib.crypto_kem_dec(ss, ct, sk) != 0:
            raise RuntimeError("NTRU+ decapsulation failed")
        return bytes(ss)

    def seal(self, public_key: bytes, payload: bytes, aad: bytes) -> bytes:
        kem_ct, shared = self.encapsulate(public_key)
        key = h256(b"NTRUPLUS-KDF", shared, aad)
        nonce = os.urandom(12)
        dem = AESGCM(key).encrypt(nonce, payload, aad)
        return kem_ct + nonce + dem

    def open(self, secret_key: bytes, sealed: bytes, aad: bytes) -> bytes:
        kem_ct = sealed[: self.CIPHERTEXT_BYTES]
        nonce = sealed[self.CIPHERTEXT_BYTES : self.CIPHERTEXT_BYTES + 12]
        dem = sealed[self.CIPHERTEXT_BYTES + 12 :]
        shared = self.decapsulate(secret_key, kem_ct)
        key = h256(b"NTRUPLUS-KDF", shared, aad)
        return AESGCM(key).decrypt(nonce, dem, aad)


def generate_ed25519_pairs(count: int):
    return [(sk := ed25519.Ed25519PrivateKey.generate(), sk.public_key()) for _ in range(count)]


def generate_paillier():
    return paillier.generate_paillier_keypair(n_length=PAILLIER_BITS)


def paillier_width(public_key) -> int:
    return (public_key.nsquare.bit_length() + 7) // 8


def serialize_paillier(ciphertexts: Iterable, public_key) -> bytes:
    width = paillier_width(public_key)
    return b"".join(fixed_int(item.ciphertext(be_secure=False), width) for item in ciphertexts)


@dataclass
class RSAEnvelopeKey:
    private: rsa.RSAPrivateKey

    @property
    def public(self):
        return self.private.public_key()


def generate_rsa_envelopes(count: int) -> list[RSAEnvelopeKey]:
    return [RSAEnvelopeKey(rsa.generate_private_key(public_exponent=65537, key_size=RSA_BITS)) for _ in range(count)]


def rsa_hybrid_seal(public_key, payload: bytes, aad: bytes) -> bytes:
    key = os.urandom(32)
    wrapped = public_key.encrypt(
        key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=aad),
    )
    nonce = os.urandom(12)
    return wrapped + nonce + AESGCM(key).encrypt(nonce, payload, aad)


def rsa_hybrid_open(private_key, sealed: bytes, aad: bytes) -> bytes:
    width = private_key.key_size // 8
    wrapped, nonce, body = sealed[:width], sealed[width : width + 12], sealed[width + 12 :]
    key = private_key.decrypt(
        wrapped,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=aad),
    )
    return AESGCM(key).decrypt(nonce, body, aad)


@dataclass
class DSAGroup:
    p: int
    q: int
    g: int
    h: int
    elgamal_secret: int
    elgamal_public: int

    @classmethod
    def generate(cls) -> "DSAGroup":
        key = DSA.generate(3072)
        p, q, g = int(key.p), int(key.q), int(key.g)
        h_secret = int.from_bytes(os.urandom(64), "big") % q or 1
        h = pow(g, h_secret, p)
        x = int.from_bytes(os.urandom(64), "big") % q or 1
        return cls(p=p, q=q, g=g, h=h, elgamal_secret=x, elgamal_public=pow(g, x, p))

    @property
    def element_bytes(self) -> int:
        return (self.p.bit_length() + 7) // 8

    def commit(self, message: int, randomness: int) -> int:
        return (pow(self.g, message % self.q, self.p) * pow(self.h, randomness % self.q, self.p)) % self.p

    def prove_opening(self, commitment: int, message: int, randomness: int, context: bytes):
        wm = int.from_bytes(os.urandom(64), "big") % self.q
        wr = int.from_bytes(os.urandom(64), "big") % self.q
        announcement = (pow(self.g, wm, self.p) * pow(self.h, wr, self.p)) % self.p
        challenge = int.from_bytes(
            h256(
                b"RZKPV",
                fixed_int(commitment, self.element_bytes),
                fixed_int(announcement, self.element_bytes),
                context,
            ),
            "big",
        ) % self.q
        return announcement, (wm + challenge * message) % self.q, (wr + challenge * randomness) % self.q

    def verify_opening(self, commitment: int, proof, context: bytes) -> bool:
        announcement, zm, zr = proof
        challenge = int.from_bytes(
            h256(
                b"RZKPV",
                fixed_int(commitment, self.element_bytes),
                fixed_int(announcement, self.element_bytes),
                context,
            ),
            "big",
        ) % self.q
        left = (pow(self.g, zm, self.p) * pow(self.h, zr, self.p)) % self.p
        right = (announcement * pow(commitment, challenge, self.p)) % self.p
        return left == right

    def elgamal_seal(self, payload: bytes, aad: bytes) -> bytes:
        k = int.from_bytes(os.urandom(64), "big") % self.q or 1
        c1 = pow(self.g, k, self.p)
        shared = pow(self.elgamal_public, k, self.p)
        key = h256(b"ELGAMAL-KDF", fixed_int(shared, self.element_bytes), aad)
        nonce = os.urandom(12)
        return fixed_int(c1, self.element_bytes) + nonce + AESGCM(key).encrypt(nonce, payload, aad)

    def elgamal_open(self, sealed: bytes, aad: bytes) -> bytes:
        width = self.element_bytes
        c1 = int.from_bytes(sealed[:width], "big")
        nonce, body = sealed[width : width + 12], sealed[width + 12 :]
        shared = pow(c1, self.elgamal_secret, self.p)
        key = h256(b"ELGAMAL-KDF", fixed_int(shared, width), aad)
        return AESGCM(key).decrypt(nonce, body, aad)
