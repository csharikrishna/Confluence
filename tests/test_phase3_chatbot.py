"""
Unit and Integration Tests for Phase 3 — Minimal Chatbot Interface
Tests location matching, grounding prompt construction, /ask endpoint, /chat UI,
unregistered location graceful fallback, and CLI execution.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from chatbot import (
    match_location,
    build_grounding_prompt,
    ask_coastal_assistant,
    LOCATION_ALIASES,
    CHATBOT_ANSWER_CACHE,
)


class TestPhase3Chatbot(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        CHATBOT_ANSWER_CACHE.clear()

    def test_location_matching_canonical_and_aliases(self):
        # Chennai
        self.assertEqual(match_location("is it safe to fish near Chennai right now")["name"], "Chennai Coast")
        self.assertEqual(match_location("How are the waves in Madras?")["name"], "Chennai Coast")

        # Visakhapatnam
        self.assertEqual(match_location("Conditions near Vizag coast")["name"], "Visakhapatnam Coast")
        self.assertEqual(match_location("Visakhapatnam port swell")["name"], "Visakhapatnam Coast")

        # Kochi
        self.assertEqual(match_location("Can artisanal boats sail from Kochi today?")["name"], "Kochi Coast")
        self.assertEqual(match_location("Weather report for Cochin")["name"], "Kochi Coast")

        # Mumbai
        self.assertEqual(match_location("Any high wave alerts in Mumbai?")["name"], "Mumbai Coast")
        self.assertEqual(match_location("Water conditions in Bombay harbor")["name"], "Mumbai Coast")

        # Kolkata / Sundarbans
        self.assertEqual(match_location("Storm potential in the Sundarbans?")["name"], "Kolkata / Sundarbans Coast")
        self.assertEqual(match_location("Tidal conditions around Kolkata")["name"], "Kolkata / Sundarbans Coast")

    def test_location_matching_unregistered_queries(self):
        self.assertIsNone(match_location("What is the weather in Delhi right now?"))
        self.assertIsNone(match_location("How is the traffic in Bengaluru?"))
        self.assertIsNone(match_location("Is it raining in Paris?"))
        self.assertIsNone(match_location(""))
        self.assertIsNone(match_location(None))

    def test_build_grounding_prompt_structure(self):
        mock_snapshot = {
            "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
            "timestamp_utc": "2026-09-06T12:00:00Z",
            "data": {"weather": {"temperature_c": 31.0, "wind_speed_kmh": 15.0}},
            "meta": {"derived_insights": {"heat_index_c": 38.0}},
        }
        mock_alerts = [{"id": "heat_index_warning", "severity": "warning", "message": "High heat"}]

        messages = build_grounding_prompt("Is it safe to fish?", mock_snapshot, mock_alerts)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("ONLY the verified real-time data", messages[0]["content"])
        self.assertIn("PROACTIVE SAFETY ALERT", messages[0]["content"])

        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("OPERATIONAL COASTAL BRIEFING", messages[1]["content"])
        self.assertIn("Chennai Coast", messages[1]["content"])
        self.assertIn("heat_index_warning", messages[1]["content"])
        self.assertIn("Is it safe to fish?", messages[1]["content"])

    def test_unregistered_location_graceful_handling(self):
        res = ask_coastal_assistant("What is the weather in New Delhi?")
        self.assertIsNone(res["location_matched"])
        self.assertIsNone(res["coordinates"])
        self.assertIsNone(res["grounding_data"])
        self.assertIn("Chennai Coast", res["answer"])
        self.assertIn("Mumbai Coast", res["answer"])
        self.assertEqual(len(res["available_locations"]), 5)

    @patch("chatbot.call_nvidia_llm")
    @patch("chatbot.fetch_grounding_context")
    def test_ask_coastal_assistant_registered_mocked(self, mock_fetch, mock_llm):
        mock_fetch.return_value = (
            {
                "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
                "data": {"weather": {"temperature_c": 30.0}},
                "meta": {},
            },
            [{"id": "high_wave", "severity": "warning"}],
        )
        mock_llm.return_value = "Fishing is safe today with waves under 1.2 meters."

        res = ask_coastal_assistant("Is it safe to fish in Chennai right now?")
        self.assertEqual(res["location_matched"], "Chennai Coast")
        self.assertEqual(res["coordinates"]["lat"], 13.08)
        self.assertEqual(res["answer"], "Fishing is safe today with waves under 1.2 meters.")
        self.assertEqual(len(res["active_alerts"]), 1)
        self.assertIsNotNone(res["grounding_data"])

    def test_post_ask_empty_question(self):
        resp = self.client.post("/ask", json={"question": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot be empty", resp.json()["detail"]["message"])

    def test_post_ask_unregistered_location(self):
        resp = self.client.post("/ask", json={"question": "How is the weather in Hyderabad?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["location_matched"])
        self.assertIn("registered monitoring stations", data["answer"])
        self.assertEqual(len(data["available_locations"]), 5)

    @patch("app.ask_coastal_assistant")
    def test_post_ask_registered_location(self, mock_assistant):
        mock_assistant.return_value = {
            "question": "Can small craft sail from Kochi?",
            "location_matched": "Kochi Coast",
            "location_used": "Kochi Coast",
            "coordinates": {"lat": 9.93, "lon": 76.26},
            "answer": "Winds are 12 km/h and wave heights are 0.9m. Conditions are favorable.",
            "active_alerts": [],
            "grounding_data": {"location": {"name": "Kochi Coast"}},
        }

        resp = self.client.post("/ask", json={"question": "Can small craft sail from Kochi?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["location_matched"], "Kochi Coast")
        self.assertIn("favorable", data["answer"])
        self.assertIn("grounding_data", data)

    def test_get_chat_ui(self):
        resp = self.client.get("/chat")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("Confluence Coastal AI", resp.text)
        self.assertIn("Grounded Telemetry Context", resp.text)
        self.assertIn("Active Stations", resp.text)

    def test_root_includes_phase3_endpoints(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("/ask", data["endpoints"])
        self.assertIn("/chat", data["endpoints"])
        self.assertEqual(data["chat_ui"], "/chat")
        self.assertIn("primary_llm_engine", data)

    @patch("chatbot.call_gemini_llm")
    @patch("chatbot.is_gemini_available", return_value=True)
    @patch("chatbot.fetch_grounding_context")
    def test_ask_coastal_assistant_gemini_routing(self, mock_fetch, mock_avail, mock_gemini):
        mock_fetch.return_value = (
            {
                "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
                "data": {"weather": {"temperature_c": 30.0}},
                "meta": {},
            },
            [],
        )
        mock_gemini.return_value = ("Gemini: Seas are calm under 1.0m.", "gemini-3.6-flash")

        res = ask_coastal_assistant("Is it safe in Chennai?", provider="gemini")
        self.assertEqual(res["location_matched"], "Chennai Coast")
        self.assertEqual(res["answer"], "Gemini: Seas are calm under 1.0m.")
        self.assertEqual(res["llm_provider"], "gemini")
        self.assertEqual(res["llm_model"], "gemini-3.6-flash")

    @patch("chatbot.call_nvidia_llm")
    @patch("chatbot.call_gemini_llm")
    @patch("chatbot.is_gemini_available", return_value=True)
    @patch("chatbot.fetch_grounding_context")
    def test_ask_coastal_assistant_gemini_fallback_to_nvidia(
        self, mock_fetch, mock_avail, mock_gemini, mock_nvidia
    ):
        mock_fetch.return_value = (
            {
                "location": {"name": "Mumbai Coast", "lat": 18.94, "lon": 72.84},
                "data": {"weather": {"temperature_c": 29.0}},
                "meta": {},
            },
            [],
        )
        # Gemini fails with RuntimeError
        mock_gemini.side_effect = RuntimeError("All candidate models 503")
        mock_nvidia.return_value = "NVIDIA NIM fallback response."

        res = ask_coastal_assistant("Is it safe in Mumbai?", provider="gemini")
        self.assertEqual(res["location_matched"], "Mumbai Coast")
        self.assertEqual(res["answer"], "NVIDIA NIM fallback response.")
        self.assertEqual(res["llm_provider"], "nvidia")
        self.assertTrue(mock_nvidia.called)

    def test_post_ask_question_too_long(self):
        long_q = "Is it safe in Chennai? " + ("word " * 120)
        resp = self.client.post("/ask", json={"question": long_q})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("string_too_long", str(resp.json()))

    @patch("chatbot.call_gemini_llm")
    @patch("chatbot.is_gemini_available", return_value=True)
    @patch("chatbot.fetch_grounding_context")
    def test_chatbot_answer_cache_hit(self, mock_fetch, mock_avail, mock_gemini):
        mock_fetch.return_value = (
            {
                "location": {"name": "Chennai Coast", "lat": 13.08, "lon": 80.27},
                "data": {"weather": {"temperature_c": 30.0}},
                "meta": {},
            },
            [],
        )
        mock_gemini.return_value = ("Fresh Gemini Answer", "gemini-3.5-flash-lite")

        # 1st call: Miss (calls Gemini)
        r1 = ask_coastal_assistant("Can I visit Chennai Marina today?", provider="gemini")
        self.assertFalse(r1["cache_hit"])
        self.assertEqual(mock_gemini.call_count, 1)

        # 2nd call with same query: Hit (returns cached result without invoking Gemini)
        r2 = ask_coastal_assistant("can i visit chennai marina today?", provider="gemini")
        self.assertTrue(r2["cache_hit"])
        self.assertEqual(mock_gemini.call_count, 1)  # NOT incremented!
        self.assertEqual(r2["answer"], "Fresh Gemini Answer")


if __name__ == "__main__":
    unittest.main()


