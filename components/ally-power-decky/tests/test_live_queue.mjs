import assert from 'node:assert/strict';
import test from 'node:test';
import { LiveQueue } from '../src/live-queue.ts';

test('rapid slider events send only the final watts', async () => {
  const calls = [];
  const q = new LiveQueue(async c => { calls.push(c); return c; });
  for(let watts=3;watts<=25;watts++) q.enqueue({kind:'tdp',watts});
  await q.flush();
  assert.deepEqual(calls,[{kind:'tdp',watts:25}]); q.stop();
});
test('in-flight CPU changes are serialized, retaining the last user choice', async () => {
  const calls = []; let release; let concurrent=0; let maximum=0;
  const gate = new Promise(r => { release=r; });
  const q = new LiveQueue(async c => {
    concurrent++; maximum=Math.max(maximum,concurrent); calls.push(c);
    if(calls.length===1) await gate;
    concurrent--; return c;
  });
  q.enqueue({kind:'cpu',config:{smt:true,cores:8,threads:16}});
  const running=q.flush();
  for(let cores=7;cores>=2;cores--) q.enqueue({kind:'cpu',config:{smt:false,cores,threads:cores}});
  release(); await running;
  assert.equal(maximum,1); assert.equal(calls.length,2);
  assert.deepEqual(calls[1].config,{smt:false,cores:2,threads:2}); q.stop();
});
test('native Steam handoff removes pending TDP writes but preserves CPU changes', async () => {
  const calls=[]; const q=new LiveQueue(async c=>{calls.push(c);return c});
  q.enqueue({kind:'tdp',watts:30});
  q.enqueue({kind:'cpu',config:{smt:false,cores:4,threads:4}});
  q.enqueue({kind:'mode',enabled:false});
  await q.flush();
  assert.deepEqual(calls.map(c=>c.kind),['mode','cpu']); q.stop();
});
test('failed TDP acquisition never executes queued TDP but CPU remains usable', async () => {
  const calls=[]; const q=new LiveQueue(async c=>{
    calls.push(c);if(c.kind==='mode') throw Error('blocked');return c;
  });
  q.enqueue({kind:'mode',enabled:true});q.enqueue({kind:'tdp',watts:20});
  q.enqueue({kind:'cpu',config:{smt:true,cores:8,threads:16}});
  await q.flush();
  assert.deepEqual(calls.map(c=>c.kind),['mode','cpu']);q.stop();
});
test('unloading drops queued writes', async () => {
  const calls=[];const q=new LiveQueue(async c=>calls.push(c));
  q.enqueue({kind:'tdp',watts:20});q.stop();await q.flush();
  assert.equal(calls.length,0);
});
