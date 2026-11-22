"""Small offline tests: no internet, camera or YOLO download required."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision
from server import SeatStatus, OccupancySnapshot


class FakeTensor:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, index):
        return self.value[index]

    def tolist(self):
        return self.value


class FakeBox:
    def __init__(self, label, coords, confidence):
        self.cls = FakeTensor([label])
        self.xyxy = FakeTensor([FakeTensor(coords)])
        self.conf = FakeTensor([confidence])


class FakePrediction:
    def __init__(self, boxes):
        self.boxes = boxes


class FakeYOLO:
    names = {0: "person", 56: "chair"}

    def __init__(self):
        self.calls = []
        self.people = [FakeBox(0, [55, 80, 125, 200], .92)]
        self.chairs = [FakeBox(56, [280, 150, 350, 210], .83),
                       FakeBox(56, [50, 150, 120, 210], .94)]

    def predict(self, frame, *, conf, classes=None, verbose=False):
        self.calls.append(classes)
        return [FakePrediction(self.people if classes == [0] else self.chairs)]


class SeatTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((360, 640, 3), dtype=np.uint8)
        self.fake = FakeYOLO()

    def test_sorted_map_and_regions(self):
        result = vision._seat_map_from_frame(self.frame, self.fake)
        self.assertEqual([s["seat_id"] for s in result["seats"]], ["S01", "S02"])
        self.assertEqual(result["seats"][0]["chair_box"], [50, 150, 120, 210])
        self.assertLess(result["seats"][0]["box"][1], 150)

    def test_detect_chairs_saves_original_and_new_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.jpg"
            cv2.imwrite(str(path), self.frame)
            with patch.object(vision, "_yolo", return_value=self.fake):
                result = vision.detect_chairs(str(path), directory)
            self.assertEqual(result["detected_chairs"], 2)
            self.assertTrue((Path(directory) / "detected_seats.jpg").exists())
            self.assertTrue((Path(directory) / "detected_chairs.json").exists())
            regions, ref_size = vision.load_seats(str(Path(directory) / "seats.json"))
            self.assertEqual(len(regions), 2)
            self.assertEqual(ref_size, (640, 360))

    def test_no_person_does_not_invent_confidence(self):
        seats = [{"seat_id": "S01", "box": [40, 90, 130, 220]}]
        result = vision.match_people_to_seats(seats, [])
        self.assertEqual(result[0]["status"], "available")
        self.assertIsNone(result[0]["confidence"])

    def test_person_matches_single_seat(self):
        seats = [{"seat_id": "S01", "box": [40, 90, 130, 220]},
                 {"seat_id": "S02", "box": [270, 90, 370, 220]}]
        people = [{"box": [50, 70, 120, 210], "confidence": .91}]
        result = vision.match_people_to_seats(seats, people)
        self.assertEqual([s["status"] for s in result], ["occupied", "available"])
        self.assertAlmostEqual(result[0]["confidence"], .91)

    def test_nearby_unmatched_seat_is_unknown(self):
        seats = [{"seat_id": "S01", "box": [40, 90, 130, 220]},
                 {"seat_id": "S02", "box": [120, 90, 210, 220]}]
        people = [{"box": [60, 70, 150, 210], "confidence": .9}]
        result = vision.match_people_to_seats(seats, people)
        self.assertEqual(result[0]["status"], "occupied")
        self.assertEqual(result[1]["status"], "unknown")

    def test_hold_frames(self):
        last, miss = {}, {}
        for i in range(4):
            row = [{"seat_id": "S01", "status": "occupied" if i == 0 else "available", "confidence": .9 if i == 0 else None}]
            vision._hold_occupied(row, last, miss, 2)
            self.assertEqual(row[0]["status"], "available" if i == 3 else "occupied")
            if i in (1, 2):
                self.assertTrue(row[0]["stabilized"])

    def test_auto_map_photo_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.jpg"
            cv2.imwrite(str(path), self.frame)
            with patch.object(vision, "_yolo", return_value=self.fake):
                report = vision.analyze_occupancy(str(path), None, output_dir=directory,
                                                  auto_map=True, room_id="R101", camera_id="C7")
            self.assertEqual(report["counts"], {"total": 2, "occupied": 1, "available": 1, "unknown": 0})
            self.assertEqual(report["seats"][0]["coordinates"],
                             {"x1": 50, "y1": 150, "x2": 120, "y2": 210})
            self.assertEqual(report["seats"][0]["occupancy"], "occupied")
            self.assertEqual(report["room_id"], "R101")
            self.assertTrue((Path(directory) / "latest.json").exists())
            self.assertEqual(len((Path(directory) / "frames.jsonl").read_text().splitlines()), 1)
            self.assertEqual(json.loads((Path(directory) / "seats.json").read_text())["camera_id"], "C7")
            OccupancySnapshot.model_validate(report)

    def test_manual_seat_file_still_works(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.jpg"
            cv2.imwrite(str(path), self.frame)
            seats = Path(directory) / "my-seats.json"
            seats.write_text(json.dumps({"reference_width": 640, "reference_height": 360,
                                         "seats": [{"id": "S01", "box": [40, 90, 130, 220]}]}))
            with patch.object(vision, "_yolo", return_value=self.fake):
                report = vision.analyze_occupancy(str(path), str(seats), output_dir=directory)
            self.assertEqual(report["counts"]["occupied"], 1)
            self.assertIsNone(report["seats"][0]["chair_confidence"])

    def test_API_backward_compatibility(self):
        model = SeatStatus(seat_id="S01", status="available", confidence=None)
        self.assertEqual(model.seat_id, "S01")
        with self.assertRaises(ValueError):
            SeatStatus(seat_id="S01", status="occupied", occupancy="available")

    def test_requires_either_calibration_or_auto(self):
        with self.assertRaises(ValueError):
            vision.analyze_occupancy("none.jpg", None)
        with self.assertRaises(ValueError):
            vision.analyze_occupancy("none.jpg", "seats.json", auto_map=True)


if __name__ == "__main__":
    unittest.main()
