import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compiled = ts.transpileModule(fs.readFileSync(new URL('../src/queue.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.ESNext}}).outputText;
const {LatestQueue}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const wait=ms=>new Promise(r=>setTimeout(r,ms));
test('rapid colors coalesce into one final complete configuration',async()=>{
 const calls=[];const queue=new LatestQueue(async c=>{calls.push(c);return c;},10);
 queue.enqueue({colors:['red'],brightness:10});queue.enqueue({colors:['blue'],brightness:90});
 await queue.idle();assert.deepEqual(calls,[{colors:['blue'],brightness:90}]);
});
test('input arriving during a request is serialized and last input wins',async()=>{
 const calls=[];let release;let active=0;let maximum=0;
 const queue=new LatestQueue(async c=>{active++;maximum=Math.max(maximum,active);calls.push(c);
  if(c===1)await new Promise(r=>release=r);active--;return c;},1);
 queue.enqueue(1);await wait(10);queue.enqueue(2);queue.enqueue(3);release();
 await queue.idle();assert.deepEqual(calls,[1,3]);assert.equal(maximum,1);
});
test('close discards unsent inputs but waits for an already sent request',async()=>{
 const calls=[];let release;
 const queue=new LatestQueue(async c=>{calls.push(c);await new Promise(r=>release=r);return c;},1);
 queue.enqueue(1);await wait(10);queue.enqueue(2);const closed=queue.close();
 release();await closed;queue.enqueue(3);await wait(5);assert.deepEqual(calls,[1]);
});
test('failed request does not discard newer user input',async()=>{
 const calls=[];const errors=[];
 const queue=new LatestQueue(async c=>{calls.push(c);if(c===1){await wait(15);throw Error('rejected');}return c;},1);
 queue.onResult=(_,error)=>{if(error)errors.push(error);};queue.enqueue(1);await wait(5);queue.enqueue(2);
 await queue.idle();assert.deepEqual(calls,[1,2]);assert.equal(errors.length,1);
});
test('drop cancels a not-yet-sent change without a hardware request',async()=>{
 const calls=[];const queue=new LatestQueue(async c=>calls.push(c),30);
 queue.enqueue(1);queue.drop();await queue.idle();await wait(35);assert.deepEqual(calls,[]);
});
