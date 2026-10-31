import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import fs from 'node:fs';
import ts from 'typescript';

function load() {
  let now = 0;
  const calls = [];
  const model = {state:{session_ready:true,session_lease:'a',tdp_enabled:false,
    desktop_busy:false,competitors:[]}, native:true, recoveryResult:null,cpuResult:null};
  const context = vm.createContext({exports:{}, console, setTimeout, clearTimeout,
    setInterval:()=>0, clearInterval:()=>{}, Date:{now:()=>now}});
  const compile = (name, target) => {
    const source=fs.readFileSync(new URL('../src/'+name,import.meta.url),'utf8');
    const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,
      target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX}}).outputText;
    vm.runInContext(code,target);
  };
  const queueContext=vm.createContext({exports:{},setTimeout,clearTimeout});
  compile('live-queue.ts',queueContext);
  context.require = name => {
    if(name==='react') return {};
    if(name==='react/jsx-runtime') return {jsx:()=>null,jsxs:()=>null};
    if(name==='@decky/ui') return {Router:{MainRunningApp:{appid:'0'}}};
    if(name==='./live-queue') return queueContext.exports;
    if(name==='@decky/api') return {definePlugin:()=>{},callable:method=>async(...args)=>{
      calls.push({method,args});
      if(method==='recover_pending' && model.recoveryResult) return await model.recoveryResult();
      if(method==='recover_cpu' && model.cpuResult) return await model.cpuResult();
      return structuredClone(model.state);
    }};
    if(name==='./steam-tdp') return {nativeTdpAvailable:()=>true,nativeTdpEnabled:()=>model.native,
      nativeTdpKey:()=>JSON.stringify({enabled:model.native,limit:15}),
      setNativeTdp:async value=>{calls.push({native:value});model.native=value;}};
    throw Error(name);
  };
  compile('index.tsx',context);
  return {model,calls,run:expression=>vm.runInContext(expression,context),time:value=>{now=value;}};
}

test('fresh user CPU action carries its lease to backend',async()=>{
  const app=load();await app.run('refresh()');app.calls.length=0;
  await app.run('execute({kind:"cpu",config:{smt:true,cores:8,threads:16},lease:"a"})');
  assert.equal(app.calls[0].method,'set_cpu');assert.equal(app.calls[0].args[1],'a');
});

test('old queued action cannot acquire TDP after lease changed',async()=>{
  const app=load();await app.run('refresh()');
  app.model.state.session_lease='b';await app.run('refresh()');app.calls.length=0;
  await assert.rejects(app.run('execute({kind:"mode",enabled:true,lease:"a"})'),/descartada/);
  assert.equal(app.calls.length,0);
});

test('resume discards pending CPU/TDP and waits before giving native TDP back',async()=>{
  const app=load();await app.run('refresh()');app.model.native=false;
  app.run('acquiredNativeTdp=true; controls.enqueue({kind:"cpu",config:{smt:false,cores:4,threads:4},lease:"a"})');
  app.time(6000);app.model.state={...app.model.state,session_ready:false,session_lease:'b'};
  await app.run('refresh()');
  assert.equal(app.run('controls.pending'),false);
  assert.equal(app.calls.some(c=>'native' in c),false);
  app.time(8000);app.model.state.session_ready=true;await app.run('refresh()');
  assert.deepEqual(app.calls.filter(c=>'native' in c),[{native:true}]);
});

test('pending countdown does not prematurely hand native TDP back',async()=>{
  const app=load();app.model.native=false;app.run('acquiredNativeTdp=true');
  app.model.state.recovery={enabled:true,pending:true,id:'r',phase:'countdown',seconds:5};
  await app.run('refresh()');
  assert.equal(app.calls.some(c=>'native' in c),false);
  assert.equal(app.calls.some(c=>c.method==='recover_pending'),false);
});

test('one-shot recovers TDP first and reads Steam again before CPU',async()=>{
  const app=load();app.model.native=false;
  app.model.state.recovery={enabled:true,pending:true,id:'r',phase:'ready'};
  app.model.recoveryResult=async()=>{
    // A native profile/setting can change while the TDP RPC is awaited.
    app.model.native=true;
    return {...app.model.state,recovery:{enabled:true,pending:false,id:'r',phase:'cpu-check'}};
  };
  app.model.cpuResult=async()=>({...app.model.state,recovery:{enabled:true,pending:false,phase:'skipped'}});
  await app.run('refresh()');
  const requests=app.calls.filter(c=>c.method?.startsWith('recover'));
  assert.deepEqual(requests.map(c=>c.method),['recover_pending','recover_cpu']);
  assert.equal(requests[0].args[2].native_tdp,false);
  assert.equal(requests[1].args[2].native_tdp,true);
});

test('manual edit during awaited TDP recovery prevents later automatic CPU',async()=>{
  const app=load();app.model.native=false;
  app.model.state.recovery={enabled:true,pending:true,id:'r',phase:'ready'};
  app.model.recoveryResult=async()=>{
    app.run('editRevision++');
    return {...app.model.state,recovery:{enabled:true,pending:false,id:'r',phase:'cpu-check'}};
  };
  await app.run('refresh()');
  assert.equal(app.calls.some(c=>c.method==='recover_cpu'),false);
});
