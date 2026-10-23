import { useEffect, useRef, useState } from "react";
import { PanelSection, PanelSectionRow, SliderField, ToggleField, staticClasses } from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { LiveQueue, type Command, type CPUConfig } from "./live-queue";
import { nativeTdpAvailable, nativeTdpEnabled, setNativeTdp } from "./steam-tdp";

type Config = CPUConfig & { watts: number };
type State = {
  active: boolean; desktop_busy: boolean; gaming: boolean; error: string;
  competitors: string[]; host: { supported: boolean; reason: string; product: string };
  power: { ac: boolean; max_watts: number; battery: number | null };
  cpu: CPUConfig & { max_cores: number; max_threads: number };
  limits: { stapm: number; fast: number; slow: number };
  tdp_enabled: boolean; tdp_target: number | null; cpu_target: CPUConfig | null;
  temperature: number | null; tdp_verified: boolean; tdp_note: string; warning: string;
};
const getState = callable<[], State>("get_state");
const setCPU = callable<[config: CPUConfig], State>("set_cpu");
const setTDP = callable<[watts: number], State>("set_tdp");
const setTdpMode = callable<[enabled: boolean], State>("set_tdp_mode");
let acquiredNativeTdp = false;

async function execute(command: Command): Promise<State> {
  let next: State;
  if (command.kind === "cpu") next = await setCPU(command.config);
  else if (command.kind === "tdp") {
    if (nativeTdpEnabled() !== false) {
      controls.dropTdp();
      next = await setTdpMode(false);
      next.error = "Steam ha retomado su TDP. El control TDP del plugin se ha desactivado.";
    } else next = await setTDP(command.watts);
  } else if (command.enabled) {
    const previous = nativeTdpEnabled();
    await setNativeTdp(false);
    try {
      next = await setTdpMode(true);
      if (next.error) throw new Error(next.error);
      acquiredNativeTdp = true;
    } catch (error) {
      if (previous !== null) await setNativeTdp(previous);
      throw error;
    }
  } else {
    next = await setTdpMode(false);
    if (!next.error) { await setNativeTdp(true); acquiredNativeTdp = false; }
  }
  if (next.error) { controls.publish(next, next.error); throw new Error(next.error); }
  return next;
}
const controls = new LiveQueue<State>(execute);
let reading = false;
async function refresh() {
  if (reading || controls.pending) return;
  reading = true;
  try {
    let next = await getState();
    if (controls.pending) return;
    if (next.tdp_enabled && nativeTdpEnabled() !== false) {
      controls.dropTdp();
      next = await setTdpMode(false);
      next.warning = "Steam ha retomado el TDP; CPU y SMT siguen disponibles.";
      acquiredNativeTdp = false;
    } else if (next.tdp_enabled) {
      acquiredNativeTdp = true;
    } else if (acquiredNativeTdp && !next.desktop_busy && next.competitors.length === 0) {
      // A worker exit or mode handoff must not leave native Steam TDP disabled.
      await setNativeTdp(true);
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
    const next = { ...configRef.current, ...change };
    configRef.current = next; setConfig(next); setError("");
    controls.enqueue({ kind: "cpu", config: { smt: next.smt, cores: next.cores, threads: next.threads } });
  }
  function editTDP(watts: number) {
    const next = { ...configRef.current, watts: Math.round(watts) };
    configRef.current = next; setConfig(next); setError("");
    controls.enqueue({ kind: "tdp", watts: next.watts });
  }
  function editMode(enabled: boolean) {
    setSteamOff(enabled); setError(""); controls.enqueue({ kind: "mode", enabled });
  }
  if (!state) return <PanelSection title="Ally Power"><Note>{error || "Leyendo el estado de tu Ally…"}</Note></PanelSection>;
  const blocked = !state.host.supported || !state.gaming || state.desktop_busy || state.competitors.length > 0;
  const maxThreads = config.smt ? Math.min(state.cpu.max_threads, config.cores * 2) : config.cores;
  const status = error || state.error || state.warning ||
    (!state.host.supported ? state.host.reason :
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
        description="Independiente del control TDP. Los cambios se aplican automáticamente."
        onChange={smt => editCPU({ smt, threads: smt ? Math.min(state.cpu.max_threads, configRef.current.cores * 2) : configRef.current.cores })} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Núcleos activos" value={config.cores} min={1} max={state.cpu.max_cores}
        step={1} showValue disabled={blocked}
        onChange={value => { const cores = Math.round(value), current = configRef.current;
          editCPU({ cores, threads: current.smt ? Math.max(cores, Math.min(current.threads, cores * 2)) : cores }); }} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Hilos activos" value={config.threads} min={config.cores} max={Math.max(config.cores + 1, maxThreads)}
        step={1} showValue disabled={blocked || maxThreads === config.cores}
        onChange={value => editCPU({ threads: Math.min(maxThreads, Math.round(value)) })} /></PanelSectionRow>
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
      if (acquiredNativeTdp) {
        void setTdpMode(false).then(next => {
          if (!next.error) return setNativeTdp(true);
        }).catch(() => {});
      }
    },
  };
});
