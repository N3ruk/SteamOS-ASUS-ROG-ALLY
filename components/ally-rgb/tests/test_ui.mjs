import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

// Isolated hook/Decky boundary: execute the real component and its event handlers,
// without starting Steam, importing Steam's webpack modules, or touching LEDs.
function harness() {
  const colors=['#112233','#445566','#778899','#aabbcc'];
  const state = {version:'1.0.0',supported:true,active:true,paused:false,editor_zone:'all',
    config:{enabled:true,brightness:50,resume:true,zone:'all',zones:colors.map(color=>({
      effect:'solid',speed:50,color,transition_colors:['#ff0000','#0000ff']}))},
    actual:{hex:[...colors],brightness:128,sleep:false},
    conflicts:[],error:'',warning:'',battery:75};
  const applied=[];
  const slots=[]; let cursor=0; const cleanups=[]; const timers=[];
  let queued=null; let queue;
  const api={
    get_state:async()=>structuredClone(state),
    apply_config:async value=>{applied.push(structuredClone(value));state.config=structuredClone(value);state.editor_zone=value.zone;return structuredClone(state);},
    select_zone:async zone=>{state.config.zone=zone;state.editor_zone=zone;return structuredClone(state);},
    release_control:async()=>state, pause:async()=>state, resume:async()=>state,
  };
  const react={
    useState(value){const index=cursor++;if(!(index in slots))slots[index]=value;
      return [slots[index],next=>{slots[index]=typeof next==='function'?next(slots[index]):next;}];},
    useRef(value){const index=cursor++;if(!(index in slots))slots[index]={current:value};return slots[index];},
    useEffect(fn){const index=cursor++;if(!(index in slots)){slots[index]=true;cleanups.push(fn());}},
  };
  const jsx=(type,props,key)=>({type,props:props||{},key});
  const components=Object.fromEntries(['PanelSection','PanelSectionRow','SliderField','ToggleField','DropdownItem'].map(name=>[name,name]));
  class Queue {
    constructor(execute){this.execute=execute;queue=this;}
    get pending(){return queued!==null;}
    enqueue(value){queued=value;this.onResult(null,'',true);}
    async flush(){const value=queued;if(!value)return;const result=await this.execute(value);queued=null;this.onResult(result,'',false);}
    drop(){queued=null;} async idle(){} async close(){queued=null;}
  }
  const modules={
    react, '@decky/ui':{...components,staticClasses:{Title:'title'}},
    'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'Fragment'},
    '@decky/api':{callable:name=>api[name],definePlugin:fn=>fn},
    './queue':{LatestQueue:Queue},
  };
  function load(relative) {
    const source=fs.readFileSync(new URL('../src/'+relative,import.meta.url),'utf8');
    const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
    const result={};
    vm.runInNewContext(code,{exports:result,require:name=>modules[name],window:{SteamClient:{System:{
      RegisterForOnSuspendRequest:()=>()=>{},RegisterForOnResumeFromSuspend:()=>()=>{}}}},
      setInterval:fn=>{timers.push(fn);return timers.length;},clearInterval:()=>{},console,structuredClone});
    return result;
  }
  modules['./config']=load('config.ts');
  const plugin=load('index.tsx').default();
  const render=()=>{cursor=0;return plugin.content.type();};
  const walk=(tree,predicate,out=[])=>{
    if(!tree||typeof tree!=='object')return out;
    if(Array.isArray(tree)){for(const item of tree)walk(item,predicate,out);return out;}
    if(predicate(tree))out.push(tree);
    walk(tree.props?.children,predicate,out);return out;
  };
  return {
    state,applied,render,
    async ready(){render();await new Promise(resolve=>setImmediate(resolve));},
    find(tree,label){return walk(tree,node=>node.props.label===label)[0];},
    all(tree,type){return walk(tree,node=>node.type===type);},
    async flush(){await queue.flush();},
    async poll(){timers[0]();await new Promise(resolve=>setImmediate(resolve));},
    remount(){for(const cleanup of cleanups.splice(0))cleanup?.();slots.length=0;return render();},
  };
}

test('zone selection is controlled and survives confirmation, polling and panel remount',async()=>{
  const h=harness();await h.ready();
  const selector=h.find(h.render(),'Zonas');assert.equal(selector.props.controlled,true);
  selector.props.onChange({data:'zone3'});
  assert.equal(h.find(h.render(),'Zonas').props.selectedOption,'zone3');
  await h.flush();await h.poll();
  assert.equal(h.find(h.render(),'Zonas').props.selectedOption,'zone3');
  assert.equal(h.find(h.remount(),'Zonas').props.selectedOption,'zone3');
  const before=[...h.state.config.zones.map(zone=>zone.color)];
  h.find(h.render(),'Rojo').props.onChange(250);await h.flush();
  const after=h.applied.at(-1).zones.map(zone=>zone.color);
  assert.equal(after[2],'#fa8899');
  for(const i of [0,1,3])assert.equal(after[i],before[i]);
});

test('RGB handlers use the latest selected group even if Steam retains an older callback',async()=>{
  const h=harness();await h.ready();
  const slider=h.find(h.render(),'Verde');
  h.find(h.render(),'Zonas').props.onChange({data:'pair34'});
  slider.props.onChange(240);await h.flush();
  const value=h.applied.at(-1);
  assert.equal(value.zone,'pair34');
  assert.deepEqual(value.zones.map(zone=>zone.color),['#112233','#445566','#77f099','#aaf0cc']);
});

test('transition exposes six sliders and independent initial/final colors',async()=>{
  const h=harness();await h.ready();
  h.find(h.render(),'Efecto').props.onChange({data:'gradient'});await h.flush();
  const sliders=h.all(h.render(),'SliderField').filter(node=>['Rojo','Verde','Azul'].includes(node.props.label));
  assert.equal(sliders.length,6);
  sliders[1].props.onChange(80);await h.flush();
  assert.deepEqual(h.applied.at(-1).zones[0].transition_colors,['#ff5000','#0000ff']);
  const updated=h.all(h.render(),'SliderField').filter(node=>['Rojo','Verde','Azul'].includes(node.props.label));
  updated[3].props.onChange(70);await h.flush();
  assert.deepEqual(h.applied.at(-1).zones[0].transition_colors,['#ff5000','#4600ff']);
});

test('simplified panel omits removed controls and sends recovery preference with the last configuration',async()=>{
  const h=harness();await h.ready();const tree=h.render();
  for(const label of ['Color rápido','Nombre del perfil','Perfil guardado','Animación al suspender'])assert.equal(h.find(tree,label),undefined);
  assert.equal(h.all(tree,'ButtonItem').length,0);
  h.find(tree,'Recuperar al despertar/encender').props.onChange(false);await h.flush();
  assert.equal(h.applied.at(-1).resume,false);
  assert.equal(h.applied.at(-1).brightness,50);
});

test('selecting another zone loads its own effect without applying or replacing the previous one',async()=>{
  const h=harness();await h.ready();
  h.find(h.render(),'Zonas').props.onChange({data:'zone1'});await h.flush();
  h.find(h.render(),'Efecto').props.onChange({data:'wave'});await h.flush();
  const count=h.applied.length;
  h.find(h.render(),'Zonas').props.onChange({data:'zone2'});await h.flush();
  assert.equal(h.applied.length,count);
  assert.equal(h.find(h.render(),'Efecto').props.selectedOption,'solid');
  h.find(h.render(),'Rojo').props.onChange(240);await h.flush();
  assert.equal(h.applied.at(-1).zones[0].effect,'wave');
  assert.equal(h.applied.at(-1).zones[1].effect,'solid');
  h.find(h.render(),'Zonas').props.onChange({data:'zone1'});await h.flush();
  assert.equal(h.find(h.render(),'Efecto').props.selectedOption,'wave');
});

test('pending effect edit is retained when editor selection changes before queue flush',async()=>{
  const h=harness();await h.ready();
  h.find(h.render(),'Zonas').props.onChange({data:'zone1'});await h.flush();
  h.find(h.render(),'Efecto').props.onChange({data:'breath'});
  h.find(h.render(),'Zonas').props.onChange({data:'zone2'});
  await h.flush();
  assert.equal(h.applied.length,1);
  assert.equal(h.state.config.zones[0].effect,'breath');
  assert.equal(h.state.config.zones[1].effect,'solid');
  assert.equal(h.find(h.render(),'Zonas').props.selectedOption,'zone2');
});

test('mixed group selection preserves independent effects until an explicit group edit',async()=>{
  const h=harness();await h.ready();
  h.find(h.render(),'Zonas').props.onChange({data:'zone1'});await h.flush();
  h.find(h.render(),'Efecto').props.onChange({data:'breath'});await h.flush();
  h.find(h.render(),'Zonas').props.onChange({data:'pair12'});await h.flush();
  assert.equal(h.find(h.render(),'Efecto').props.selectedOption,'mixed');
  assert.equal(h.state.config.zones[0].effect,'breath');
  assert.equal(h.state.config.zones[1].effect,'solid');
  h.find(h.render(),'Efecto').props.onChange({data:'gradient'});await h.flush();
  assert.deepEqual(h.state.config.zones.map(zone=>zone.effect),['gradient','gradient','solid','solid']);
});
