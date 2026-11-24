"""Offline smoke tests: booking reminders, profile inbox persistence, and authorization shape.
No MongoDB connection is created.
"""
from __future__ import annotations

import copy
import threading
import unittest
from datetime import timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend import study_circles_api as mod


class FakeCursor(list):
    def sort(self, keys):
        return FakeCursor(sorted(self, key=lambda d: tuple(d.get(k) for k, _ in keys)))


class FakeCollection:
    def __init__(self):
        self.docs = {}
        self.lock = threading.Lock()

    def insert_one(self, doc):
        with self.lock:
            if doc["_id"] in self.docs:
                raise mod.DuplicateKeyError("duplicate")
            self.docs[doc["_id"]] = copy.deepcopy(doc)
            return SimpleNamespace(inserted_id=doc["_id"])

    def find(self, query, projection=None):
        with self.lock:
            found = []
            for value in self.docs.values():
                doc = copy.deepcopy(value)
                if "$or" in query:
                    who = query["$or"][0]["organizer_roll"]
                    guest = query["$or"][1]["invitees.roll_number"]
                    match = doc["organizer_roll"] == who or any(i["roll_number"] == guest for i in doc["invitees"])
                else:
                    match = all(doc.get(k) == v for k, v in query.items())
                if match:
                    if projection is not None:
                        doc.pop("_id", None)
                    found.append(doc)
            return FakeCursor(found)

    def find_one(self, query, projection=None):
        with self.lock:
            for value in self.docs.values():
                if all(value.get(k) == v for k, v in query.items()):
                    doc = copy.deepcopy(value)
                    if projection is not None:
                        doc.pop("_id", None)
                    return doc
        return None

    def update_one(self, query, update):
        with self.lock:
            for value in self.docs.values():
                if value["booking_id"] != query["booking_id"]:
                    continue
                if "organizer_roll" in query and value["organizer_roll"] != query["organizer_roll"]:
                    continue
                if "reminders.9" in query and len(value.get("reminders", [])) >= 10:
                    continue
                if "$push" in update:
                    value.setdefault("reminders", []).append(copy.deepcopy(update["$push"]["reminders"]))
                    return SimpleNamespace(modified_count=1)
                if "$set" in update:
                    invite_query = query["invitees"]["$elemMatch"]
                    for inv in value["invitees"]:
                        if inv["roll_number"] == invite_query["roll_number"] and inv["status"] == invite_query["status"]:
                            inv["status"] = update["$set"]["invitees.$.status"]
                            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    def delete_one(self, query):
        with self.lock:
            for key, doc in list(self.docs.items()):
                if doc["booking_id"] == query["booking_id"] and doc["organizer_roll"] == query["organizer_roll"]:
                    del self.docs[key]
                    return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeCollection()
        self.old_get_collection = mod.get_collection
        mod.get_collection = lambda: self.database
        api = FastAPI()
        api.include_router(mod.router)
        self.client = TestClient(api)
        day = (mod.now_local() + timedelta(days=1)).date().isoformat()
        self.input = {"organizer_roll": "STUDENTA", "date": day, "slot": "18:00", "topic": "Graph algorithms", "invitees": ["STUDENTB", "STUDENTC"]}
        response = self.client.post("/api/study-circles/bookings", json=self.input)
        self.assertEqual(response.status_code, 201, response.text)
        self.booking_id = response.json()["booking"]["booking_id"]

    def tearDown(self):
        mod.get_collection = self.old_get_collection

    def remind(self, sender="STUDENTA", message="Meet at the entrance by 5:55 PM"):
        return self.client.post(f"/api/study-circles/bookings/{self.booking_id}/remind", json={"sender_roll": sender, "message": message})

    def test_reminder_persists_for_each_invitee(self):
        response = self.remind()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["recipients"], 2)
        for recipient in ("STUDENTB", "STUDENTC"):
            details = self.client.get("/api/study-circles/bookings", params={"user_roll": recipient})
            self.assertEqual(details.status_code, 200)
            bookings = details.json()["bookings"]
            self.assertEqual(len(bookings), 1)
            reminders = bookings[0]["reminders"]
            self.assertEqual(len(reminders), 1)
            self.assertIn(recipient, reminders[0]["recipient_rolls"])
            self.assertIn("entrance", reminders[0]["message"])

    def test_no_other_student_can_remind_or_respond(self):
        self.assertEqual(self.remind(sender="STUDENTC").status_code, 403)
        response = self.client.post(f"/api/study-circles/bookings/{self.booking_id}/respond", json={"user_roll": "STRANGER", "decision": "ACCEPTED"})
        self.assertEqual(response.status_code, 409)

    def test_declined_invitee_not_notified(self):
        response = self.client.post(f"/api/study-circles/bookings/{self.booking_id}/respond", json={"user_roll": "STUDENTC", "decision": "DECLINED"})
        self.assertEqual(response.status_code, 200)
        sent = self.remind()
        self.assertEqual(sent.json()["recipients"], 1)
        reminders = self.client.get("/api/study-circles/bookings", params={"user_roll": "STUDENTC"}).json()["bookings"][0]["reminders"]
        self.assertNotIn("STUDENTC", reminders[-1]["recipient_rolls"])

    def test_empty_and_message_limit(self):
        self.assertEqual(self.remind(message="   ").status_code, 422)
        self.assertEqual(self.remind(message="x" * 221).status_code, 422)
        for _ in range(10):
            self.assertEqual(self.remind().status_code, 200)
        self.assertEqual(self.remind().status_code, 409)

    def test_cancel_removes_inbox_entry(self):
        self.assertEqual(self.remind().status_code, 200)
        self.client.delete(f"/api/study-circles/bookings/{self.booking_id}", params={"user_roll": "STUDENTA"})
        result = self.client.get("/api/study-circles/bookings", params={"user_roll": "STUDENTB"})
        self.assertEqual(result.json()["bookings"], [])


if __name__ == "__main__":
    unittest.main()
