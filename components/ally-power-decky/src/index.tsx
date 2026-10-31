import { useEffect, useRef, useState } from "react";
import { PanelSection, PanelSectionRow, SliderField, ToggleField, staticClasses, Router } from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { LiveQueue, type Command, type CPUConfig } from "./live-queue";
import { nativeTdpAvailable, nativeTdpEnabled, nativeTdpKey, setNativeTdp } from "./steam-tdp";

type Config = CPUConfig & { watts: number };
type State = {
  active: boolean; desktop_busy: boolean; gaming: boolean; error: string;
  competitors: string[]; host: { supported: boolean; reason: string; product: string };
  power: { ac: boolean; max_watts: number; battery: number | null };
  cpu: CPUConfig & { max_cores: number; max_threads: number };
  limits: { stapm: number; fast: number; slow: number };
  tdp_enabled: boolean; tdp_target: number | null; cpu_target: CPUConfig | null;
  temperature: number | null; tdp_verified: boolean; tdp_note: string; warning: string;
  session_ready: boolean; session_lease: string;
  recovery?: {enabled:boolean;pending:boolean;id:string|null;phase:string;seconds:number|null;reason:string;wants_tdp:boolean};
};
type SessionContext = {awake:boolean;game_id:string;native_tdp:boolean|null;tdp_key:string};
function sessionContext(): SessionContext {
  const suspend = (globalThis as unknown as {SuspendResumeStore?:{m_bSuspending?:boolean}}).SuspendResumeStore;
  return {awake:suspend?.m_bSuspending !== true,game_id:String(Router?.MainRunningApp?.appid || "0"),
    native_tdp:nativeTdpEnabled(),tdp_key:nativeTdpKey()};
}
const frontendReady = callable<[context:SessionContext], State>("frontend_ready");
const setRecovery = callable<[enabled:boolean], State>("set_recovery");
const recoverPending = callable<[identity:string,lease:string,context:SessionContext], State>("recover_pending");
const recoverCpu = callable<[identity:string,lease:string,context:SessionContext], State>("recover_cpu");
const setCPU = callable<[config: CPUConfig, lease?: string], State>("set_cpu");
const setTDP = callable<[watts: number, lease?: string], State>("set_tdp");
const setTdpMode = callable<[enabled: boolean, lease?: string], State>("set_tdp_mode");
let acquiredNativeTdp = false;
let latest: State | null = null;
let lastPulse = Date.now();
let editRevision = 0;
const sessionAvailable = () => !!latest?.session_ready && Date.now() - lastPulse < 4000;

async function execute(command: Command): Promise<State> {
  const allowed = () => sessionAvailable() && command.lease === latest?.session_lease;
  if (!allowed()) throw new Error("Orden anterior a una transición descartada. Espera 10 s y vuelve a ajustar.");
  let next: State;
  if (command.kind === "cpu") next = await setCPU(command.config, command.lease);
  else if (command.kind === "tdp") {
    if (nativeTdpEnabled() !== false) {
      controls.dropTdp();
      next = await setTdpMode(false);
      next.error = "Steam ha retomado su TDP. El control TDP del plugin se ha desactivado.";
    } else next = await setTDP(command.watts, command.lease);
  } else if (command.enabled) {
    const previous = nativeTdpEnabled();
    acquiredNativeTdp = previous === true || acquiredNativeTdp;
    try {
      await setNativeTdp(false, allowed);
      if (!allowed()) throw new Error("Transición durante la adquisición de TDP.");
      next = await setTdpMode(true, command.lease);
      if (next.error) throw new Error(next.error);
      acquiredNativeTdp = true;
    } catch (error) {
      if (previous !== null && allowed()) await setNativeTdp(previous, allowed);
      throw error;
    }
  } else {
    next = await setTdpMode(false);
    if (!next.error) { await setNativeTdp(true, allowed); acquiredNativeTdp = false; }
  }
  if (next.error) { controls.publish(next, next.error); throw new Error(next.error); }
  return next;
}
const controls = new LiveQueue<State>(execute);
let reading = false;
async function refresh() {
  if (Date.now() - lastPulse > 4000) {
    controls.discard();
    if (latest) latest = { ...latest, session_ready: false };
  }
  if (reading || controls.pending) return;
  reading = true;
  try {
    let next = await frontendReady(sessionContext());
    if (controls.pending) return;
    lastPulse = Date.now();
    if (!next.session_ready || next.session_lease !== latest?.session_lease) controls.discard();
    latest = next;
    if (!next.session_ready) { controls.publish(next); return; }
    if (next.recovery?.phase === "ready" && next.recovery.id) {
      const observedEdit = editRevision;
      const identity = next.recovery.id;
      next = await recoverPending(identity,next.session_lease,sessionContext());
      if (controls.pending || observedEdit !== editRevision) return;
      latest = next;
      if (next.recovery?.phase === "cpu-check" && sessionAvailable()) {
        // Re-read Steam AFTER TDP, before reducing CPU as the final stage.
        next = await recoverCpu(identity,next.session_lease,sessionContext());
        if (controls.pending || observedEdit !== editRevision) return;
        latest = next;
      }
    }
    if (next.recovery?.pending || ["applying","cpu-check","applying-cpu"].includes(next.recovery?.phase || "")) {
      controls.publish(next); return; // Do not hand TDP back while its one-shot is pending.
    }
    if (next.tdp_enabled && nativeTdpEnabled() !== false) {
      controls.dropTdp();
      next = await setTdpMode(false);
      next.warning = "Steam ha retomado el TDP; CPU y SMT siguen disponibles.";
      acquiredNativeTdp = false;
    } else if (next.tdp_enabled) {
      acquiredNativeTdp = true;
    } else if (acquiredNativeTdp && !next.desktop_busy && next.competitors.length === 0) {
      // A worker exit or mode handoff must not leave native Steam TDP disabled.
      await setNativeTdp(true, sessionAvailable);
      acquiredNativeTdp = false;
    }
    controls.publish(next);
  } catch (error) { controls.publish(null, String(error)); }
  finally { reading = false; }
}

const Note = ({ children, warning = false }: { children: React.ReactNode; warning?: boolean }) => (
  <PanelSectionRow><div style={{ fontSize: 12, lineHeight: 1.5, marginBottom: 12,
    padding: "10px 12px", borderRadius: 6, background: warning ? "#503a21" : "#23303d",
    color: "#f3f5f7", overflowWrap: "anywhere" }}>{children}</div></PanelSectionRow>
);

function Content() {
  const [state, setState] = useState<State | null>(null);
  const [config, setConfig] = useState<Config>({ watts: 15, smt: true, cores: 8, threads: 16 });
  const configRef = useRef(config);
  const [error, setError] = useState("");
  const [steamOff, setSteamOff] = useState(false);
  useEffect(() => {
    const unsubscribe = controls.subscribe((next, failure) => {
      setError(failure);
      if (!next || controls.pending) return;
      setState(next); setSteamOff(next.tdp_enabled);
      const cpu = next.cpu_target ?? next.cpu;
      const current = { smt: cpu.smt, cores: cpu.cores, threads: cpu.threads,
        watts: Math.max(3, Math.min(Math.round(next.tdp_target ?? (next.limits.stapm || 15)), next.power.max_watts)) };
      configRef.current = current; setConfig(current);
    });
    void refresh();
    return unsubscribe;
  }, []);
  function editCPU(change: Partial<CPUConfig>) {
    editRevision++;
    const next = { ...configRef.current, ...change };
    configRef.current = next; setConfig(next); setError("");
    controls.enqueue({ kind: "cpu", lease: state?.session_lease, config: { smt: next.smt, cores: next.cores, threads: next.threads } });
  }
  function editTDP(watts: number) {
    editRevision++;
    const next = { ...configRef.current, watts: Math.round(watts) };
    configRef.current = next; setConfig(next); setError("");
    controls.enqueue({ kind: "tdp", watts: next.watts, lease: state?.session_lease });
  }
  function editMode(enabled: boolean) {
    editRevision++;
    setSteamOff(enabled); setError(""); controls.enqueue({ kind: "mode", enabled, lease: state?.session_lease });
  }
  async function editRecovery(enabled:boolean) {
    editRevision++;
    try { const next=await setRecovery(enabled); latest=next;controls.publish(next); }
    catch(error) {setError(String(error));}
  }
  if (!state) return <PanelSection title="Ally Power"><Note>{error || "Leyendo el estado de tu Ally…"}</Note></PanelSection>;
  const blocked = !state.session_ready || !state.host.supported || !state.gaming || state.desktop_busy || state.competitors.length > 0;
  const maxThreads = config.smt ? Math.min(state.cpu.max_threads, config.cores * 2) : config.cores;
  const status = error || state.error || state.warning ||
    (!state.session_ready ? "Esperando 10 s de sesión estable." :
      !state.host.supported ? state.host.reason :
      !state.gaming ? "Disponible en modo Gaming." :
      state.desktop_busy ? "Cierra Ally Power de escritorio conservando los ajustes." :
      state.competitors.length ? `Desactiva el gestor: ${state.competitors.join(", ")}.` : "");
  return <>
    <PanelSection>
      <Note><strong>{state.power.ac ? "Con cargador" : "Batería"}</strong>
        {state.power.battery !== null ? ` · ${state.power.battery}%` : ""}
        {state.temperature !== null ? ` · ${state.temperature} °C` : ""}<br />
        TDP configurado: <strong>{state.limits.stapm || "—"} W</strong><br />
        CPU: {state.cpu.cores} núcleos · {state.cpu.threads} hilos · SMT {state.cpu.smt ? "activado" : "desactivado"}
        {state.recovery?.enabled && <div style={{marginTop:6}}>
          {state.recovery.phase === "countdown" ? `Recuperando ajustes en ${state.recovery.seconds} s…` :
           state.recovery.phase === "restored" ? "Ajustes previos recuperados." : state.recovery.reason}
        </div>}
        {status && <div role="status" style={{ color: "#ffcf8a", marginTop: 6 }}>{status}</div>}</Note>
    </PanelSection>
    <PanelSection title="Ajuste manual">
      <PanelSectionRow><ToggleField label="TDP de Steam desactivado" checked={steamOff}
        disabled={blocked || !nativeTdpAvailable()}
        description={!nativeTdpAvailable() ? "API TDP de Steam no disponible. CPU y SMT siguen disponibles." :
          steamOff ? "TDP controlado por el plugin. Al apagarlo vuelve a Steam." : "TDP nativo de Steam. SMT, núcleos e hilos siguen disponibles."}
        onChange={editMode} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="TDP" value={config.watts} min={3} max={state.power.max_watts}
        step={1} showValue valueSuffix=" W" disabled={blocked || !steamOff} onChange={editTDP} /></PanelSectionRow>
      <PanelSectionRow><ToggleField label="SMT" checked={config.smt} disabled={blocked}
        description={state.recovery?.enabled ? "Antes de suspender se activa CPU completa; al despertar se recuperan tus ajustes tras la espera." :
          "Independiente del TDP. Antes de suspender se activa la CPU completa; vuelve a ajustarla tras despertar."}
        onChange={smt => editCPU({ smt, threads: smt ? Math.min(state.cpu.max_threads, configRef.current.cores * 2) : configRef.current.cores })} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Núcleos activos" value={config.cores} min={1} max={state.cpu.max_cores}
        step={1} showValue disabled={blocked}
        onChange={value => { const cores = Math.round(value), current = configRef.current;
          editCPU({ cores, threads: current.smt ? Math.max(cores, Math.min(current.threads, cores * 2)) : cores }); }} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Hilos activos" value={config.threads} min={config.cores} max={Math.max(config.cores + 1, maxThreads)}
        step={1} showValue disabled={blocked || maxThreads === config.cores}
        onChange={value => editCPU({ threads: Math.min(maxThreads, Math.round(value)) })} /></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Suspensión">
      <PanelSectionRow><ToggleField label="Recuperar ajustes al despertar" checked={state.recovery?.enabled || false}
        description="Recupera una vez los ajustes que controlaba POWER tras 10 s de Gaming estable. No aplica perfiles al arrancar."
        onChange={enabled=>void editRecovery(enabled)} /></PanelSectionRow>
    </PanelSection>
  </>;
}
export default definePlugin(() => {
  const timer = setInterval(() => void refresh(), 2000);
  return {
    name: "Ally Power", titleView: <div className={staticClasses.Title}>Ally Power</div>, content: <Content />,
    icon: <svg viewBox="0 0 24 24" fill="none" width="20" height="20" aria-hidden="true">
      <path d="M7 6h10l4 11c.5 2-2 3-3 1l-2-3H8l-2 3c-1 2-3.5 1-3-1L7 6Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="M7 9v4m-2-2h4m7-1h.1m2 2h.1M12 8l-1 3h2l-1 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>,
    onDismount() {
      clearInterval(timer); controls.stop();
      if (acquiredNativeTdp && sessionAvailable()) {
        void setTdpMode(false).then(next => {
          if (!next.error) return setNativeTdp(true, sessionAvailable);
        }).catch(() => {});
      }
    },
  };
});
