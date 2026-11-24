"""Offline API smoke tests using a fake in-memory collection (no MongoDB writes)."""
import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend import study_circles_api as mod


class Cursor(list):
    def sort(self, keys):
        return Cursor(sorted(self, key=lambda x: tuple(x.get(k) for k, _ in keys)))


class Collection:
    def __init__(self):
        self.docs = {}
        self.lock = threading.Lock()

    def insert_one(self, doc):
        with self.lock:
            if doc['_id'] in self.docs:
                raise mod.DuplicateKeyError('already exists')
            self.docs[doc['_id']] = copy.deepcopy(doc)
        return SimpleNamespace(inserted_id=doc['_id'])

    def find(self, query, projection=None):
        with self.lock:
            docs = [copy.deepcopy(v) for v in self.docs.values()]
        results = []
        for doc in docs:
            if '$or' in query:
                roll = query['$or'][0]['organizer_roll']
                invited = query['$or'][1]['invitees.roll_number']
                passed = doc['organizer_roll'] == roll or any(i['roll_number'] == invited for i in doc['invitees'])
            else:
                passed = all(doc.get(k) == v for k, v in query.items())
            if passed:
                if projection:
                    doc = {k: v for k, v in doc.items() if k != '_id' and (not projection.get('slot') or k=='slot')}
                results.append(doc)
        return Cursor(results)

    def find_one(self, query, projection=None):
        found = self.find(query, projection)
        return found[0] if found else None

    def update_one(self, query, update):
        with self.lock:
            for doc in self.docs.values():
                if doc['booking_id'] == query['booking_id']:
                    invite_query = query['invitees']['$elemMatch']
                    for i in doc['invitees']:
                        if i['roll_number'] == invite_query['roll_number'] and i['status']== invite_query['status']:
                            i['status'] = update['$set']['invitees.$.status']
                            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    def delete_one(self, query):
        with self.lock:
            for key, doc in self.docs.items():
                if doc['booking_id'] == query['booking_id'] and doc['organizer_roll'] == query['organizer_roll']:
                    del self.docs[key]
                    return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class StudyCirclesTests(unittest.TestCase):
    def setUp(self):
        self.col = Collection()
        self.old_get = mod.get_collection
        mod.get_collection = lambda: self.col
        app = FastAPI()
        app.include_router(mod.router)
        self.client = TestClient(app)
        self.day = (mod.now_local() + timedelta(days=1)).date().isoformat()
        self.data = {"organizer_roll":"STUDENTA","date":self.day,"slot":"18:00","topic":"CS601 Algorithms", "invitees":["STUDENTB"]}

    def tearDown(self):
        mod.get_collection = self.old_get

    def test_fcfs_invites_cancel(self):
        booking = self.client.post('/api/study-circles/bookings',json=self.data)
        self.assertEqual(booking.status_code, 201, booking.text)
        ref=booking.json()['booking']['booking_id']
        other=self.client.post('/api/study-circles/bookings',json={**self.data,'organizer_roll':'STUDENTC','invitees':[]})
        self.assertEqual(other.status_code,409)
        slots=self.client.get('/api/study-circles/slots',params={'date':self.day}).json()
        self.assertIn('18:00',slots['booked_slots'])
        invited=self.client.get('/api/study-circles/bookings',params={'user_roll':'STUDENTB'}).json()['bookings']
        self.assertEqual(len(invited),1)
        accept=self.client.post(f'/api/study-circles/bookings/{ref}/respond',json={'user_roll':'STUDENTB','decision':'ACCEPTED'})
        self.assertEqual(accept.status_code,200)
        self.assertEqual(accept.json()['booking']['invitees'][0]['status'],'ACCEPTED')
        again=self.client.post(f'/api/study-circles/bookings/{ref}/respond',json={'user_roll':'STUDENTB','decision':'DECLINED'})
        self.assertEqual(again.status_code,409)
        wrong=self.client.delete(f'/api/study-circles/bookings/{ref}',params={'user_roll':'STUDENTC'})
        self.assertEqual(wrong.status_code,403)
        right=self.client.delete(f'/api/study-circles/bookings/{ref}',params={'user_roll':'STUDENTA'})
        self.assertEqual(right.status_code,200)
        self.assertEqual(self.client.post('/api/study-circles/bookings',json=self.data).status_code,201)

    def test_concurrent_same_slot_only_one_success(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda n:self.client.post('/api/study-circles/bookings',json={**self.data,'organizer_roll':n,'invitees':[]}).status_code,['STUDENTA','STUDENTC']))
        self.assertEqual(sorted(results),[201,409])

    def test_rejects_invalid_input(self):
        self.assertEqual(self.client.post('/api/study-circles/bookings',json={**self.data,'invitees':['STUDENTA']}).status_code,422)
        self.assertEqual(self.client.post('/api/study-circles/bookings',json={**self.data,'slot':'18:30'}).status_code,422)
        self.assertEqual(self.client.post('/api/study-circles/bookings',json={**self.data,'date':'2020-01-01'}).status_code,422)


if __name__=='__main__':
    unittest.main()
