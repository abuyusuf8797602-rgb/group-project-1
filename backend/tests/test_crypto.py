"""Checks that the primitives are used correctly.

Run inside the api container (it already has `cryptography` installed):

    docker compose -f docker-compose.base44.yml exec -T api python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

from cryptography.exceptions import InvalidTag

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import crypto  # noqa: E402


class SymmetricEncryptionTests(unittest.TestCase):
    def test_roundtrip(self):
        key = crypto.new_key()
        blob = crypto.encrypt(key, b"hello signing world", b"aad")
        self.assertEqual(crypto.decrypt(key, blob, b"aad"), b"hello signing world")

    def test_wrong_key_is_rejected(self):
        blob = crypto.encrypt(crypto.new_key(), b"secret")
        with self.assertRaises(InvalidTag):
            crypto.decrypt(crypto.new_key(), blob)

    def test_tampered_ciphertext_is_rejected(self):
        key = crypto.new_key()
        blob = bytearray(crypto.encrypt(key, b"secret"))
        blob[-1] ^= 0x01  # flip a bit inside the authentication tag
        with self.assertRaises(InvalidTag):
            crypto.decrypt(key, bytes(blob))

    def test_tampered_plaintext_is_rejected(self):
        key = crypto.new_key()
        blob = bytearray(crypto.encrypt(key, b"secret payload"))
        blob[crypto.NONCE_BYTES] ^= 0x01  # flip a bit inside the ciphertext
        with self.assertRaises(InvalidTag):
            crypto.decrypt(key, bytes(blob))

    def test_aad_mismatch_is_rejected(self):
        key = crypto.new_key()
        blob = crypto.encrypt(key, b"secret", b"document:one")
        with self.assertRaises(InvalidTag):
            crypto.decrypt(key, blob, b"document:two")

    def test_nonces_are_unique(self):
        key = crypto.new_key()
        nonces = {
            crypto.encrypt(key, b"same plaintext")[: crypto.NONCE_BYTES] for _ in range(200)
        }
        self.assertEqual(len(nonces), 200)


class KeyWrapTests(unittest.TestCase):
    def test_wrap_roundtrip(self):
        kek, dek = crypto.new_key(), crypto.new_key()
        wrapped = crypto.wrap_key(kek, dek, b"aad")
        self.assertEqual(crypto.unwrap_key(kek, wrapped, b"aad"), dek)

    def test_wrapped_key_is_bound_to_its_context(self):
        kek, dek = crypto.new_key(), crypto.new_key()
        wrapped = crypto.wrap_key(kek, dek, b"document:one")
        with self.assertRaises(InvalidTag):
            crypto.unwrap_key(kek, wrapped, b"document:two")


class KeyExchangeTests(unittest.TestCase):
    def test_both_sides_derive_the_same_key(self):
        alice_private, alice_public = crypto.generate_keypair()
        bob_private, bob_public = crypto.generate_keypair()
        salt = os.urandom(crypto.SALT_BYTES)

        alice_key = crypto.derive_shared_key(alice_private, bob_public, salt)
        bob_key = crypto.derive_shared_key(bob_private, alice_public, salt)
        self.assertEqual(alice_key, bob_key)

    def test_a_different_salt_gives_a_different_key(self):
        alice_private, alice_public = crypto.generate_keypair()
        bob_private, bob_public = crypto.generate_keypair()
        self.assertNotEqual(
            crypto.derive_shared_key(alice_private, bob_public, os.urandom(crypto.SALT_BYTES)),
            crypto.derive_shared_key(bob_private, alice_public, os.urandom(crypto.SALT_BYTES)),
        )

    def test_a_non_x25519_key_is_rejected(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        rsa_public_pem = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        with self.assertRaises(ValueError):
            crypto.fingerprint(rsa_public_pem)

    def test_public_key_matches_its_private_key(self):
        private, public = crypto.generate_keypair()
        self.assertEqual(crypto.public_key_from_private(private), public)
        self.assertEqual(crypto.fingerprint(public), crypto.fingerprint(public))

    def test_wrapped_key_only_opens_for_the_right_recipient(self):
        # Sender wraps for the real recipient; an impostor cannot open it.
        recipient_private, recipient_public = crypto.generate_keypair()
        ephemeral_private, ephemeral_public = crypto.generate_keypair()
        salt = os.urandom(crypto.SALT_BYTES)
        dek = crypto.new_key()

        sender_kek = crypto.derive_shared_key(ephemeral_private, recipient_public, salt)
        wrapped = crypto.wrap_key(sender_kek, dek, b"key-exchange:token:fingerprint")

        recipient_kek = crypto.derive_shared_key(
            recipient_private, ephemeral_public, salt
        )
        self.assertEqual(
            crypto.unwrap_key(recipient_kek, wrapped, b"key-exchange:token:fingerprint"),
            dek,
        )

        impostor_private, impostor_public = crypto.generate_keypair()
        impostor_kek = crypto.derive_shared_key(impostor_private, ephemeral_public, salt)
        with self.assertRaises(InvalidTag):
            crypto.unwrap_key(impostor_kek, wrapped, b"key-exchange:token:fingerprint")

        # Sanity: the impostor really was given a different public key.
        self.assertNotEqual(impostor_public, recipient_public)


class DocumentEnvelopeTests(unittest.TestCase):
    def test_ciphertext_hides_the_plaintext(self):
        blob = crypto.seal_document(b"contract v1\n", crypto.new_key())
        self.assertTrue(blob.startswith(crypto.MAGIC))
        self.assertNotIn(b"contract v1", blob)

    def test_unseal_with_the_right_key(self):
        key = crypto.new_key()
        blob = crypto.seal_document(b"contract v1\n", key)
        plaintext, encrypted = crypto.unseal_document(blob, key)
        self.assertEqual(plaintext, b"contract v1\n")
        self.assertTrue(encrypted)

    def test_legacy_plaintext_passes_through(self):
        plaintext, encrypted = crypto.unseal_document(b"old upload", crypto.new_key())
        self.assertEqual(plaintext, b"old upload")
        self.assertFalse(encrypted)

    def test_bad_envelope_version_is_rejected(self):
        key = crypto.new_key()
        blob = bytearray(crypto.seal_document(b"data", key))
        blob[len(crypto.MAGIC)] = 9
        with self.assertRaises(ValueError):
            crypto.unseal_document(bytes(blob), key)


if __name__ == "__main__":
    unittest.main()
