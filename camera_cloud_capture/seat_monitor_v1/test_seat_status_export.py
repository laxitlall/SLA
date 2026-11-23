"""Run: python -m unittest discover camera_cloud_capture/seat_monitor_v1 -p test_seat_status_export.py"""
import unittest
from seat_status_export import clean_detections, assign, counts, build_first_frame_map

class SeatOutputTests(unittest.TestCase):
    def test_overlapping_conflict_becomes_unknown(self):
        a={'bbox_xyxy':[10,20,90,110],'confidence':.7682,'state':'AVAILABLE','class':'empty-chair'}
        b={'bbox_xyxy':[10,20,90,110],'confidence':.6246,'state':'OCCUPIED','class':'occupied-chair-front'}
        cleaned,unknown=clean_detections([a,b])
        self.assertEqual(len(cleaned),1)
        self.assertEqual(unknown,1)
        self.assertEqual(cleaned[0]['state'],'UNKNOWN')
    def test_missing_detection_is_not_available(self):
        seats=[{'seat_id':'room-S01','anchor':[.1,.1]},{'seat_id':'room-S02','anchor':[.8,.8]}]
        det=[{'bbox_xyxy':[5,5,15,15],'confidence':.9,'state':'AVAILABLE'}]
        rows=assign(seats,det,100,100)
        self.assertEqual([p['status'] for p in rows],['available','unknown'])
        self.assertEqual(counts(rows),{'total':2,'available':1,'occupied':0,'unknown':1})
    def test_map_is_unconfirmed(self):
        report={'metadata':{'width':100,'height':100},'samples':[{'detections':[{'bbox_xyxy':[2,3,12,13], 'confidence':.8,'state':'AVAILABLE','class':'empty-chair'}]}]}
        proposal,_=build_first_frame_map(report,'room')
        self.assertFalse(proposal['confirmed'])
        self.assertEqual(proposal['seats'][0]['seat_id'],'room-S01')
if __name__=='__main__':unittest.main()
