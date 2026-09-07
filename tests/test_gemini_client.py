"""
Unit Tests for Confluence Gemini Client
Tests payload translation, error handling, model fallback, and integration.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from gemini_client import (
    convert_chat_messages_to_gemini_payload,
    call_gemini_llm,
    is_gemini_available,
    DEFAULT_GEMINI_MODELS,
)


class TestGeminiClient(unittest.TestCase):
    def test_convert_chat_messages_to_gemini_payload(self):
        messages = [
            {"role": "system", "content": "You are a marine safety officer."},
            {"role": "user", "content": "What is the wave height?"},
            {"role": "assistant", "content": "Wave height is 1.2m."},
            {"role": "user", "content": "Is it safe?"},
        ]
        sys_inst, contents, gen_config = convert_chat_messages_to_gemini_payload(
            messages, temperature=0.3, max_output_tokens=1000, top_p=0.9
        )

        self.assertIsNotNone(sys_inst)
        self.assertEqual(sys_inst["parts"][0]["text"], "You are a marine safety officer.")
        self.assertEqual(len(contents), 3)
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[0]["parts"][0]["text"], "What is the wave height?")
        self.assertEqual(contents[1]["role"], "model")
        self.assertEqual(contents[1]["parts"][0]["text"], "Wave height is 1.2m.")
        self.assertEqual(contents[2]["role"], "user")
        self.assertEqual(contents[2]["parts"][0]["text"], "Is it safe?")
        self.assertEqual(gen_config["temperature"], 0.3)
        self.assertEqual(gen_config["maxOutputTokens"], 1000)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"})
    def test_is_gemini_available_true(self):
        self.assertTrue(is_gemini_available())

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True)
    def test_is_gemini_available_false(self):
        self.assertFalse(is_gemini_available())

    def test_call_gemini_llm_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                call_gemini_llm([{"role": "user", "content": "test"}], api_key=None)

    @patch("requests.post")
    def test_call_gemini_llm_success_primary_model(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Navigation is safe with waves under 1.5m."}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        text, model_used = call_gemini_llm(
            [{"role": "user", "content": "Is it safe to fish?"}],
            api_key="mock-key-12345",
        )

        self.assertEqual(text, "Navigation is safe with waves under 1.5m.")
        self.assertEqual(model_used, DEFAULT_GEMINI_MODELS[0])
        self.assertTrue(mock_post.called)

    @patch("time.sleep", return_value=None)
    @patch("requests.post")
    def test_call_gemini_llm_fallback_on_503(self, mock_post, mock_sleep):
        # Primary model returns 503 twice, secondary model returns 200
        resp_503 = MagicMock()
        resp_503.status_code = 503
        resp_503.text = "High demand spike"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Secondary candidate response."}]
                    }
                }
            ]
        }

        # Model 1 fails 2 attempts with 503, Model 2 succeeds on attempt 1
        mock_post.side_effect = [resp_503, resp_503, resp_200]

        text, model_used = call_gemini_llm(
            [{"role": "user", "content": "Status update?"}],
            api_key="mock-key-12345",
            retries_per_model=2,
        )

        self.assertEqual(text, "Secondary candidate response.")
        self.assertEqual(model_used, DEFAULT_GEMINI_MODELS[1])
        self.assertEqual(mock_post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
