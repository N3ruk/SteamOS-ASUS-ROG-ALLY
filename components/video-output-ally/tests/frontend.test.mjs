import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = readFileSync(new URL('../dist/index.js', import.meta.url), 'utf8')
  .replace('export { index as default };', 'globalThis.plugin = index();');
const flush = async () => { for (let i=0; i<8; i++) await Promise.resolve(); };
const deferred = () => { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; };
function harness(read = async()=>({connectors:[],video:{gaming:false}}), select = async()=>({ok:true})) {
  const values=[], effects=[], timers=new Map(), calls=[];
  let cursor=0, initialized=false, nextTimer=1;
  const jsx=(type,props)=>({type,props});
  const ctx={ console, SP_JSX:{jsx,jsxs:jsx},
    DFL:{PanelSection:'section',PanelSectionRow:'row',ButtonItem:'button'},
    SP_REACT:{
      useState(initial) { const index=cursor++; if (!(index in values)) values[index]=initial;
        return [values[index], value=>{values[index]=value;}]; },
      useEffect(fn) { if (!initialized) effects.push(fn); },
    },
    setTimeout(fn,ms) { assert.equal(ms,2000); const id=nextTimer++;timers.set(id,fn);return id; },
    clearTimeout(id) { timers.delete(id); },
    window:{__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit:{
      connect(version,name) {
        assert.equal(name,'Video Output ALLY for DOCKs');
        return {_version:version,callable:method=>(...args)=>{
          calls.push([method,...args]);
          if (method==='get_state') return read();
          if (method==='switch_connector') return select(...args);
          throw Error('Unexpected RPC '+method);
        }};
      },
    }},
  };
  vm.createContext(ctx);vm.runInContext(source,ctx);
  const render=()=>{cursor=0;return ctx.plugin.content.type();};
  const mount=()=>{render();initialized=true;return effects.map(fn=>fn());};
  const tick=async()=>{const [id,fn]=timers.entries().next().value;timers.delete(id);await fn();};
  return {values,calls,timers,render,mount,tick};
}
function buttons(tree) {
  if (!tree || typeof tree!=='object') return [];
  if (Array.isArray(tree)) return tree.flatMap(buttons);
  return [...(tree.type==='button'?[tree]:[]), ...buttons(tree.props?.children)];
}
const state=(gaming=true)=>({connectors:[
  {id:'0:eDP-1',label:'ASUS ALLY',connected:true,hidden:false,verified:true,enabled:false},
  {id:'0:DP-10',label:'AOC 24G2WG3',connected:true,hidden:false,verified:true,enabled:true},
  {id:'0:DP-12',label:'Hidden',connected:true,hidden:true,verified:true},
  {id:'0:DP-14',label:'Gone',connected:false,hidden:false,verified:true},
],video:{gaming,busy:false,error:''}});

test('refresh waits for the previous query and stops after unmount',async()=>{
  const d=deferred();const h=harness(()=>d.promise);const clean=h.mount();
  assert.equal(h.calls.length,1);assert.equal(h.timers.size,0);
  clean.forEach(fn=>fn());d.resolve(state());await flush();
  assert.equal(h.timers.size,0);assert.equal(h.values[0],null);
});
test('refresh recovers after an error and has one cancellable timer',async()=>{
  let count=0;const h=harness(async()=>{if (++count===1)throw Error('offline');return state();});
  const clean=h.mount();await flush();assert.ok(h.values[3]);assert.equal(h.timers.size,1);
  await h.tick();assert.equal(h.values[3],'');assert.equal(h.timers.size,1);
  clean.forEach(fn=>fn());assert.equal(h.timers.size,0);
});
test('only connected visible screens appear and Desktop cannot select them',async()=>{
  const h=harness(async()=>state(false));h.mount();await flush();
  const rows=buttons(h.render());
  assert.deepEqual(rows.map(n=>n.props.children),['ASUS ALLY','AOC 24G2WG3']);
  assert.ok(rows.every(n=>n.props.disabled));
  assert.equal(rows[1].props.label,'Activa');
  assert.ok(h.calls.every(n=>n[0]==='get_state'));
});
test('selection uses the exact connector ID, disables while pending, and surfaces failure',async()=>{
  const d=deferred();const h=harness(async()=>state(),()=>d.promise);h.mount();await flush();
  buttons(h.render())[1].props.onClick();
  assert.deepEqual(h.calls.at(-1),['switch_connector','0:DP-10']);
  assert.ok(buttons(h.render()).every(n=>n.props.disabled));
  d.resolve({ok:false,error:'No native confirmation'});await flush();
  assert.equal(h.values[2],'No native confirmation');assert.equal(h.values[1],false);
  assert.ok(buttons(h.render()).every(n=>!n.props.disabled));
});
test('RPC rejection releases busy state and reports communication error',async()=>{
  const h=harness(async()=>state(),async()=>{throw Error('disconnected');});h.mount();await flush();
  buttons(h.render())[0].props.onClick();await flush();
  assert.equal(h.values[1],false);assert.match(h.values[2],/comunicar/);
});
