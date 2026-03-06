import hashlib
import hmac
import unittest

from server import parse_signature, validate_payload, verify_signature


class TestWebhookHelpers(unittest.TestCase):
    def test_parse_signature_valid(self):
        algorithm, digest = parse_signature("sha256=abc123")
        self.assertEqual(algorithm, "sha256")
        self.assertEqual(digest, "abc123")

    def test_parse_signature_invalid(self):
        self.assertEqual(parse_signature(""), (None, None))
        self.assertEqual(parse_signature("sha256"), (None, None))
        self.assertEqual(parse_signature("=abcd"), (None, None))

    def test_verify_signature(self):
        secret = "topsecret"
        body = b'{"event":"ping","data":{}}'
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_signature(secret, body, f"sha256={digest}"))
        self.assertFalse(verify_signature(secret, body, "sha256=deadbeef"))
        self.assertFalse(verify_signature(secret, body, "md5=deadbeef"))

    def test_validate_payload(self):
        valid, reason = validate_payload({"event": "ping", "data": {}})
        self.assertTrue(valid)
        self.assertEqual(reason, "")

        invalid_cases = [
            (None, "payload must be a JSON object"),
            ({}, "missing required field: event"),
            ({"event": ""}, "missing required field: event"),
            ({"event": "x"}, "missing required field: data"),
            ({"event": "x", "data": "not-object"}, "field data must be an object"),
        ]
        for payload, expected_reason in invalid_cases:
            with self.subTest(payload=payload):
                valid, reason = validate_payload(payload)
                self.assertFalse(valid)
                self.assertEqual(reason, expected_reason)


if __name__ == "__main__":
    unittest.main()
