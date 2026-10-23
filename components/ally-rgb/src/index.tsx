import { useEffect, useRef, useState, type ComponentType, type ComponentProps } from 'react';
import { PanelSection, PanelSectionRow, SliderField, ToggleField, DropdownItem, staticClasses } from '@decky/ui';
import { callable, definePlugin } from '@decky/api';
import { LatestQueue } from './queue';
import { initial, zones, indexes, channelValue, zoneChannel, transitionChannel, zoneSettings, type Config, type Zone } from './config';

type State = {
  version: string; supported: boolean; active: boolean; paused: boolean; config: Config | null;
  actual: { product: string; hex: string[]; brightness: number; sleep: boolean | null } | null;
  editor_zone: Zone; conflicts: string[]; error: string; warning: string; battery: number | null;
};
const api = {
  state: callable<[], State>('get_state'), apply: callable<[config: Config], State>('apply_config'),
  select: callable<[zone: Zone], State>('select_zone'), pause: callable<[], State>('pause'),
  resume: callable<[], State>('resume'),
};
// Steam's Dropdown supports controlled mode, omitted from @decky/ui 4.12.1's types.
// Keep the displayed editor selection on the same source of truth as saved settings.
const ControlledDropdown = DropdownItem as ComponentType<ComponentProps<typeof DropdownItem> & { controlled: boolean }>;
const effects = [ ['solid', 'Color fijo'], ['breath', 'Respiración'], ['rainbow', 'Arcoíris'], ['wave', 'Onda'], ['gradient', 'Transición'], ['battery', 'Batería'] ];
const zoneOptions = zones.map(({data, label}) => ({data, label}));
const channels = [[16, 'Rojo'], [8, 'Verde'], [0, 'Azul']] as const;
const subscribers = new Set<(state: State | null, error: string, pending: boolean) => void>();
let current: State | null = null;
let lastError = '';
let reading = false;
let hooks = false;
let hooksWarning = '';
let closing = false;
let revision = 0;
let lightingRevision = 0;
let confirmedLightingRevision = 0;
let desired: Config | null = null;
function publish(next: State | null, error = '', pending = false) {
  if (next) current = next;
  if (error || next) lastError = error || next?.error || '';
  if (!pending && !queue.pending && current) desired = fromState(current);
  for (const listener of subscribers) listener(next, lastError, pending);
}
type Request = {config: Config; apply: boolean; revision: number};
type Result = {state: State; revision: number};
const queue = new LatestQueue<Request, Result>(async request => ({
  state: await (request.apply ? api.apply(request.config) : api.select(request.config.zone)), revision: request.revision,
}));
queue.onResult = (result, error, pending) => {
  if (result && !result.state.error) confirmedLightingRevision = Math.max(confirmedLightingRevision,result.revision);
  publish(result?.state || null,error,pending);
};
async function refresh() {
  if (reading || queue.pending || closing) return;
  reading = true;
  const observedRevision = revision;
  try { const state = await api.state(); if (!queue.pending && observedRevision === revision) publish(state); }
  catch (error) { publish(null, String(error)); }
  finally { reading = false; }
}
function fromState(state: State): Config {
  if (state.config) return {...state.config,zone:state.editor_zone || state.config.zone};
  const actual = state.actual;
  return { ...initial, zone:state.editor_zone || 'all', zones:initial.zones.map((zone,i)=>({...zone,
    color:actual?.hex[i] || zone.color, transition_colors:[...zone.transition_colors]})),
    enabled:!!actual && actual.brightness > 0, brightness:actual ? Math.round(actual.brightness*100/255) : 50 };
}
const Note = ({children}: {children: React.ReactNode}) => <PanelSectionRow><div style={{padding: 12, background: '#183035', borderRadius: 8, fontSize: 12, lineHeight: 1.55}}>{children}</div></PanelSectionRow>;

function Content() {
  const [state, setState] = useState<State | null>(current);
  const [config, setConfig] = useState<Config>(desired || (current ? fromState(current) : initial));
  const draft = useRef(config);
  const [error, setError] = useState(lastError);
  const [pending, setPending] = useState(queue.pending);
  useEffect(() => {
    const listener = (next: State | null, failure: string, waiting: boolean) => {
      setPending(waiting); setError(failure);
      const confirmed = next || (!waiting && !queue.pending ? current : null);
      if (confirmed) {
        setState(confirmed);
        if (!waiting && !queue.pending) { const value = fromState(confirmed); draft.current = value; setConfig(value); }
      }
    };
    subscribers.add(listener); void refresh();
    const poll = setInterval(() => void refresh(), 2000);
    return () => { subscribers.delete(listener); clearInterval(poll); };
  }, []);
  const blocked = !state?.supported || !!state?.conflicts.length;
  function edit(change: Partial<Config>, selectionOnly = false) {
    revision++;
    if (!selectionOnly) lightingRevision++;
    const next = { ...draft.current, ...change };
    desired = next; draft.current = next; setConfig(next); setError('');
    queue.enqueue({config:next,apply:lightingRevision > confirmedLightingRevision,revision:lightingRevision});
  }
  if (!state) return <PanelSection title="ALLY RGB"><Note>{error || 'Leyendo la iluminación de tu Ally…'}</Note></PanelSection>;
  const selected = indexes(config.zone);
  const zoneConfig = config.zones[selected[0]];
  const effect = selected.every(i=>config.zones[i].effect===zoneConfig.effect) ? zoneConfig.effect : 'mixed';
  const status = error || state.error || state.warning || hooksWarning ||
    (state.conflicts.length ? 'Desactiva el otro gestor RGB: ' + state.conflicts.join(', ') :
      state.paused ? 'Pausado durante la suspensión.' : state.active ? 'ALLY RGB tiene el control.' : 'Sin control adquirido.');
  const displayColors = state.active && state.actual ? state.actual.hex : config.zones.map(zone=>zone.color);
  return <>
    <PanelSection><Note><strong>ALLY RGB</strong> · 4 zonas
      {state.battery !== null ? ` · batería ${state.battery}%` : ' · batería sin datos'}
      <div style={{display: 'flex', gap: 12, padding: '12px 0'}}>{displayColors.map((c,i) => <div key={i} title={`Zona ${i+1}: ${c}${selected.includes(i) ? ' · seleccionada' : ''}`} style={{background:c, color:'#fff', textShadow:'0 1px 3px #000', display:'grid', placeItems:'center', width:38, height:38, borderRadius:'50%', border:selected.includes(i) ? '3px solid #d1fff2' : '3px solid #556168', opacity:selected.includes(i) ? 1 : .55}}>{i+1}</div>)}</div>
      <div>{pending ? 'Aplicando el último cambio…' : status}</div>
    </Note></PanelSection>
    <PanelSection title="Iluminación">
      <PanelSectionRow><ToggleField label="Iluminación" checked={config.enabled} disabled={blocked} onChange={enabled => edit({enabled})}/></PanelSectionRow>
      <PanelSectionRow><SliderField label="Brillo" value={config.brightness} min={0} max={100} step={1} valueSuffix="%" disabled={blocked} onChange={brightness => edit({brightness:Math.round(brightness)})}/></PanelSectionRow>
      <PanelSectionRow><ControlledDropdown controlled label="Zonas" selectedOption={config.zone} rgOptions={zoneOptions} disabled={blocked} onChange={o => edit({zone:o.data as Zone},true)}/></PanelSectionRow>
      <PanelSectionRow><ControlledDropdown controlled label="Efecto" selectedOption={effect} rgOptions={[...(effect==='mixed' ? [{data:'mixed',label:'Varios efectos (conservar)'}] : []),...effects.map(([data,label]) => ({data,label}))]} disabled={blocked} onChange={o => {if(o.data!=='mixed') edit(zoneSettings(draft.current,{effect:o.data}));}}/></PanelSectionRow>
      {effect !== 'mixed' && effect !== 'solid' && effect !== 'battery' && <PanelSectionRow><SliderField label="Velocidad" value={zoneConfig.speed} min={10} max={100} step={1} valueSuffix="%" disabled={blocked} onChange={speed => edit(zoneSettings(draft.current,{speed:Math.round(speed)}))}/></PanelSectionRow>}
    </PanelSection>
    {(effect === 'solid' || effect === 'breath') && <PanelSection title="Color de las zonas seleccionadas">
      {channels.map(([shift,label]) => <PanelSectionRow key={label}><SliderField label={label} value={channelValue(zoneConfig.color,shift)} min={0} max={255} step={1} disabled={blocked} onChange={value => edit(zoneChannel(draft.current,shift,value))}/></PanelSectionRow>)}
    </PanelSection>}
    {effect === 'gradient' && zoneConfig.transition_colors.map((color, endpoint) => <PanelSection key={endpoint} title={endpoint === 0 ? 'Color inicial' : 'Color final'}>
      <PanelSectionRow><div style={{height:20, width:'100%', background:color, border:'1px solid #d1fff2', borderRadius:4}} /></PanelSectionRow>
      {channels.map(([shift,label]) => <PanelSectionRow key={label}><SliderField label={label} value={channelValue(color,shift)} min={0} max={255} step={1} disabled={blocked} onChange={value => edit(transitionChannel(draft.current,endpoint,shift,value))}/></PanelSectionRow>)}
    </PanelSection>)}
    <PanelSection>
      <PanelSectionRow><ToggleField label="Recuperar al despertar/encender" checked={config.resume} disabled={blocked} description={hooks ? 'Guarda los ajustes y los restaura al despertar o encender.' : 'Restaura al encender; Steam no ofrece la señal de despertar en esta sesión.'} onChange={resume=>edit({resume})}/></PanelSectionRow>
    </PanelSection>
  </>;
}

type Registration = {unregister?: () => void} | (() => void) | undefined;
type SystemHooks = {
  RegisterForOnSuspendRequest?: (fn: () => void) => Registration;
  RegisterForOnResumeFromSuspend?: (fn: () => void) => Registration;
};
export default definePlugin(() => {
  const registrations: Registration[] = [];
  const system = (window as unknown as {SteamClient?: {System?: SystemHooks}}).SteamClient?.System;
  let powerChain = Promise.resolve();
  try {
    if (system?.RegisterForOnSuspendRequest && system?.RegisterForOnResumeFromSuspend) {
      registrations.push(system.RegisterForOnSuspendRequest(() => {
        queue.drop(); powerChain = powerChain.then(async()=>{await queue.idle();publish(await api.pause());}).catch(e=>publish(null,String(e)));
      }));
      registrations.push(system.RegisterForOnResumeFromSuspend(() => {
        powerChain = powerChain.then(async()=>{publish(await api.resume());}).catch(e=>publish(null,String(e)));
      }));
      hooks = true;
    }
  } catch { hooksWarning = 'No se ha podido activar la recuperación automática al despertar.'; }
  return { name: 'ALLY RGB', titleView: <div className={staticClasses.Title}>ALLY RGB</div>,
    content: <Content/>, icon: <span style={{color:'#7be5cd'}}>◉</span>,
    onDismount() {
      closing = true;
      for (const item of registrations) { if (typeof item === 'function') item(); else item?.unregister?.(); }
      // Backend lifecycle owns shutdown. A late frontend unload must not release
      // a freshly reloaded backend after it restored the user's saved settings.
      void queue.close().then(()=>powerChain).catch(()=>{});
    } };
});
