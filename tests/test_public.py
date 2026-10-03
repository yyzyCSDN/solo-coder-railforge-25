import unittest
from datetime import datetime,timezone,timedelta,date
from decimal import Decimal
from railforge.api import RailForgeService
from railforge.signaling.block_occupancy import Occupancy
from railforge.consist.integrity import WagonLink,validate
from railforge.braking.brake_percentage import Vehicle,brake_percentage
from railforge.audit.trail import Trail
from railforge.planning.train_path_engine import Section,PathRequest,build
from railforge.possession.windows import Possession,conflicts as possession_conflicts
U=timezone.utc
class PublicTests(unittest.TestCase):
    def test_health(self):
        h=RailForgeService().health();self.assertEqual(h['status'],'ok');self.assertEqual(h['runtime_dependencies'],0)
    def test_block_smoke(self):
        a=Occupancy('A','B1',datetime(2026,1,1,8,tzinfo=U),datetime(2026,1,1,9,tzinfo=U),1)
        b=Occupancy('B','B1',datetime(2026,1,1,10,tzinfo=U),datetime(2026,1,1,11,tzinfo=U),1)
        self.assertEqual(RailForgeService().block_conflicts(b,[a],timedelta(minutes=5)),[])
    def test_consist_smoke(self):
        rows=[WagonLink(1,'W1',None,'W2',True),WagonLink(2,'W2','W1',None,True)]
        self.assertEqual(validate(rows),('W1','W2'))
    def test_brake_smoke(self):
        self.assertGreater(brake_percentage([Vehicle('W',100,90,True)],0),80)
    def test_audit(self):
        t=Trail();t.append('dispatcher','create','T1');t.append('supervisor','approve','T1');self.assertTrue(t.verify())
    def test_path_engine(self):
        s={'A':Section('A',30,True,2)}
        r=[PathRequest('T',datetime(2026,1,1,8,tzinfo=U),('A',),1,10)]
        self.assertIn('T',build(r,s,[],3))
    def test_possession_protected_window(self):
        a=Possession('A','S1',datetime(2026,1,1,8,tzinfo=U),datetime(2026,1,1,9,tzinfo=U),timedelta(minutes=15),timedelta(minutes=15))
        b=Possession('B','S1',datetime(2026,1,1,9,5,tzinfo=U),datetime(2026,1,1,10,tzinfo=U),timedelta(minutes=15),timedelta(minutes=15))
        self.assertEqual(possession_conflicts(b,[a]),['A'])
        c=Possession('C','S1',datetime(2026,1,1,10,tzinfo=U),datetime(2026,1,1,11,tzinfo=U),timedelta(minutes=15),timedelta(minutes=15))
        self.assertEqual(possession_conflicts(c,[a]),[])
    def test_possession_atomic_commit(self):
        svc=RailForgeService();at=datetime(2026,1,1,7,tzinfo=U)
        a=Possession('A','S1',datetime(2026,1,1,8,tzinfo=U),datetime(2026,1,1,9,tzinfo=U),timedelta(minutes=15),timedelta(minutes=15))
        r=svc.control.protect_possession('op1',a,[],'S1',at)
        self.assertEqual(r.event.payload['control_path'],'atomic');self.assertEqual(r.event.payload['status'],'committed')
        self.assertEqual(r.version,1);self.assertEqual(svc.control.store.read('S1').version,1)
        self.assertTrue(svc.control.stream.verify_chain());self.assertTrue(svc.control.trail.verify())
    def test_possession_rejection_retained(self):
        svc=RailForgeService();at=datetime(2026,1,1,7,tzinfo=U)
        a=Possession('A','S1',datetime(2026,1,1,8,tzinfo=U),datetime(2026,1,1,9,tzinfo=U),timedelta(minutes=15),timedelta(minutes=15))
        b=Possession('B','S1',datetime(2026,1,1,9,5,tzinfo=U),datetime(2026,1,1,10,tzinfo=U),timedelta(minutes=15),timedelta(minutes=15))
        occ=Occupancy('T1','B1',datetime(2026,1,1,12,tzinfo=U),datetime(2026,1,1,13,tzinfo=U),1)
        with self.assertRaises(ValueError) as ctx:
            svc.features.approve_possession('op2',b,[a],[],occ,timedelta(minutes=5),at)
        self.assertIn('A',str(ctx.exception))
        rejected=[e for e in svc.control.stream.snapshot() if e.payload.get('status')=='rejected']
        self.assertEqual(len(rejected),1);self.assertIn('A',rejected[0].payload['reason'])
        self.assertEqual(rejected[0].payload['control_path'],'atomic')
        self.assertEqual(len(svc.control.trail._rows),1)
        self.assertIsNone(svc.control.store.read('op2'))
        self.assertTrue(svc.control.stream.verify_chain());self.assertTrue(svc.control.trail.verify())
if __name__=='__main__':unittest.main()
