import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch
from py_modules.rgb import RGBLock
from py_modules.io_process import HardwareProcess

FAKE = '''import json,sys,time
for line in sys.stdin:
 r=json.loads(line)
 if r.get('brightness')==13: time.sleep(100)
 print(json.dumps({'actual':dict(device='temporary-device', backend='sysfs',colors=r.get('colors',[0]*4),brightness=r.get('brightness',0),trigger='none',readonly='--read-only' in sys.argv)}),flush=True)
 if '--read-only' in sys.argv: break
'''
class ProcessTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
  self.worker=root/'fake.py';self.worker.write_text(FAKE)
  self.lock=RGBLock(root/'lock',os.geteuid())
  self.io=HardwareProcess(self.lock,timeout=.1,worker=self.worker)
 async def asyncTearDown(self):
  await self.io.close();self.lock.release();self.tmp.cleanup()
 async def test_status_uses_write_forbidden_short_lived_process_and_no_lock(self):
  result=await self.io.state()
  self.assertTrue(result['readonly']);self.assertIsNone(self.io.process);self.assertFalse(self.lock.path.exists())
 async def test_write_requires_ownership(self):
  with self.assertRaisesRegex(RuntimeError,'bloqueo'): await self.io.write([1]*4,10)
  self.assertIsNone(self.io.process)
 async def test_child_inherits_lock_even_if_parent_releases(self):
  self.lock.acquire();await self.io.write([1]*4,10);self.lock.release()
  other=RGBLock(self.lock.path,os.geteuid())
  try:
   with self.assertRaises(BlockingIOError): other.acquire()
   await self.io.close();other.acquire()
  finally: other.release()
 async def test_hung_io_is_killed_without_blocking_event_loop(self):
  self.lock.acquire();ticks=[0]
  async def tick():
   for _ in range(20): ticks[0]+=1;await asyncio.sleep(.01)
  ticker=asyncio.create_task(tick());started=time.monotonic()
  with self.assertRaises(asyncio.TimeoutError): await self.io.write([1]*4,13)
  self.assertLess(time.monotonic()-started,.5);self.assertGreater(ticks[0],3)
  await ticker;self.assertIsNone(self.io.process)
 async def test_suspend_abort_cannot_leave_a_running_writer(self):
  self.lock.acquire();task=asyncio.create_task(self.io.write([1]*4,13));await asyncio.sleep(.025)
  self.io.abort();task.cancel()
  with self.assertRaises(asyncio.CancelledError): await task
  self.assertIsNone(self.io.process)
  with self.assertRaisesRegex(RuntimeError,'suspensión'): await self.io.write([1]*4,10)
 async def test_unkillable_helper_prevents_replacement(self):
  process=Mock(returncode=None);process._rgb_waiter=None
  async def never(): await asyncio.sleep(100)
  process.wait=AsyncMock(side_effect=never);self.io.process=process
  await self.io.close();self.assertTrue(self.io.blocked)
  with patch.object(asyncio,'create_subprocess_exec') as create:
   with self.assertRaisesRegex(RuntimeError,'no terminó'): await self.io.state()
  create.assert_not_called();process._rgb_waiter.cancel();self.io.process=None
 async def test_owned_status_still_starts_only_read_only_helper(self):
  self.lock.acquire()
  result=await self.io.state()
  self.assertTrue(result['readonly']);self.assertIsNone(self.io.process)
 async def test_real_read_only_entrypoint_rejects_write_without_touching_hardware(self):
  worker=Path(__file__).resolve().parent.parent/'py_modules/io_worker.py'
  process=await asyncio.create_subprocess_exec('/usr/bin/python3','-I',str(worker),'--read-only',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE)
  out,_=await process.communicate(b'{"action":"write","colors":[0,0,0,0],"brightness":0}\n')
  self.assertIn('no permitida',json.loads(out)['error'])

 async def test_enrollment_failure_sends_no_hardware_payload_and_reaps(self):
  from py_modules.session_io import SessionBoundary
  calls=[]
  async def reject(process):
   calls.append(process)
   raise SessionBoundary('no scope')
  self.io.scope_enroller=reject;self.lock.acquire()
  with self.assertRaisesRegex(SessionBoundary,'no scope'): await self.io.write([1]*4,10)
  self.assertEqual(len(calls),1);self.assertIsNotNone(calls[0].returncode)
  self.assertIsNone(self.io.process)
 async def test_payload_waits_for_scope_enrollment(self):
  entered=asyncio.Event();release=asyncio.Event();processes=[]
  async def enroll(process):
   processes.append(process);entered.set();await release.wait();return '/user.slice/temporary.scope'
  self.io.scope_enroller=enroll;self.lock.acquire()
  task=asyncio.create_task(self.io.write([1]*4,10));await entered.wait()
  # The fake worker emits a line for EVERY payload, so none can arrive yet.
  with self.assertRaises(asyncio.TimeoutError):
   await asyncio.wait_for(processes[0].stdout.readline(),.02)
  release.set();result=await task
  self.assertEqual(result['brightness'],10)
 async def test_frozen_scope_is_not_killed_by_close(self):
  process=Mock(returncode=None);self.io.process=process;self.io.last_scope='/user.slice/test.scope'
  with patch('py_modules.io_process.session_frozen',return_value=True): await self.io.close()
  process.kill.assert_not_called();self.assertTrue(self.io.blocked)
  process.returncode=0;process.wait=AsyncMock(return_value=0);process._rgb_waiter=None
  with patch('py_modules.io_process.session_frozen',return_value=False): await self.io.close()
  self.assertFalse(self.io.blocked);self.assertIsNone(self.io.process)
 async def test_scoped_read_timeout_waits_for_thaw(self):
  self.lock.acquire();self.io.last_scope='/user.slice/test.scope'
  task=asyncio.create_task(self.io.write([1]*4,13))
  await asyncio.sleep(.03)
  with patch('py_modules.io_process.session_frozen',return_value=True):
   await asyncio.sleep(.23);self.assertFalse(task.done())
  with self.assertRaises(asyncio.TimeoutError): await task

 async def test_sleep_during_enrollment_rejects_payload(self):
  from py_modules.session_io import SessionBoundary
  self.io.scope_enroller=AsyncMock(return_value='/user.slice/test.scope');self.lock.acquire()
  with patch('py_modules.io_process.suspend_offset',side_effect=[0,60]),patch('py_modules.io_process.session_frozen',return_value=False):
   with self.assertRaises(SessionBoundary): await self.io.write([1]*4,10)
  self.assertIsNone(self.io.process)
