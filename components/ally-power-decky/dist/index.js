const manifest = {"name":"Ally Power"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

/** Serialize hardware transactions and coalesce slider repeats to the latest value. */
class LiveQueue {
    constructor(execute) {
        this.queue = [];
        this.running = false;
        this.stopped = false;
        this.timer = null;
        this.listeners = new Set();
        this.execute = execute;
    }
    get pending() { return this.running || this.queue.length > 0; }
    subscribe(fn) { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; }
    publish(result, error = "") { for (const fn of this.listeners)
        fn(result, error); }
    dropTdp() { this.queue = this.queue.filter(c => c.kind !== "tdp"); }
    enqueue(command) {
        if (this.stopped)
            return;
        this.queue = this.queue.filter(c => c.kind !== command.kind);
        if (command.kind === "mode") {
            if (!command.enabled)
                this.dropTdp();
            this.queue.unshift(command);
        }
        else
            this.queue.push(command);
        if (this.timer)
            clearTimeout(this.timer);
        this.timer = setTimeout(() => { this.timer = null; void this.flush(); }, command.kind === "mode" ? 0 : 120);
    }
    async flush() {
        if (this.running || this.stopped)
            return;
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
        this.running = true;
        let result = null;
        let error = "";
        try {
            while (this.queue.length && !this.stopped) {
                const command = this.queue.shift();
                try {
                    result = await this.execute(command);
                    error = "";
                }
                catch (e) {
                    error = String(e);
                    if (command.kind === "mode")
                        this.dropTdp();
                }
            }
        }
        finally {
            this.running = false;
            if (!this.stopped)
                this.publish(result, error);
        }
    }
    stop() {
        this.stopped = true;
        this.queue = [];
        if (this.timer)
            clearTimeout(this.timer);
        this.listeners.clear();
    }
}

let setter;
function store() {
    return globalThis.settingsStore;
}
/** Reuse the exact settings setter used by Steam's native performance UI. */
function resolveSetter() {
    if (setter)
        return setter;
    const settings = store();
    if (!settings)
        return undefined;
    setter = DFL.findModuleChild((module) => {
        if (!module || typeof module !== "object")
            return;
        const values = Object.values(module);
        if (!values.includes(settings))
            return;
        return values.find(value => typeof value === "function" &&
            Function.prototype.toString.call(value).includes("SteamClient.Settings.SetSetting"));
    });
    return setter;
}
function nativeTdpEnabled() {
    const value = store()?.clientSettings?.steamos_tdp_limit_enabled;
    return typeof value === "boolean" ? value : null;
}
function nativeTdpAvailable() { return nativeTdpEnabled() !== null && !!resolveSetter(); }
async function setNativeTdp(enabled) {
    const update = resolveSetter();
    if (!update || nativeTdpEnabled() === null)
        throw new Error("Esta versión de Steam no expone su control TDP. Los controles de CPU siguen disponibles.");
    if (nativeTdpEnabled() === enabled)
        return;
    await update("steamos_tdp_limit_enabled", enabled);
    for (let i = 0; i < 50; i++) {
        if (nativeTdpEnabled() === enabled)
            return;
        await new Promise(resolve => setTimeout(resolve, 40));
    }
    throw new Error("Steam no confirmó el cambio de su control TDP.");
}

const getState = callable("get_state");
const setCPU = callable("set_cpu");
const setTDP = callable("set_tdp");
const setTdpMode = callable("set_tdp_mode");
let acquiredNativeTdp = false;
async function execute(command) {
    let next;
    if (command.kind === "cpu")
        next = await setCPU(command.config);
    else if (command.kind === "tdp") {
        if (nativeTdpEnabled() !== false) {
            controls.dropTdp();
            next = await setTdpMode(false);
            next.error = "Steam ha retomado su TDP. El control TDP del plugin se ha desactivado.";
        }
        else
            next = await setTDP(command.watts);
    }
    else if (command.enabled) {
        const previous = nativeTdpEnabled();
        await setNativeTdp(false);
        try {
            next = await setTdpMode(true);
            if (next.error)
                throw new Error(next.error);
            acquiredNativeTdp = true;
        }
        catch (error) {
            if (previous !== null)
                await setNativeTdp(previous);
            throw error;
        }
    }
    else {
        next = await setTdpMode(false);
        if (!next.error) {
            await setNativeTdp(true);
            acquiredNativeTdp = false;
        }
    }
    if (next.error) {
        controls.publish(next, next.error);
        throw new Error(next.error);
    }
    return next;
}
const controls = new LiveQueue(execute);
let reading = false;
async function refresh() {
    if (reading || controls.pending)
        return;
    reading = true;
    try {
        let next = await getState();
        if (controls.pending)
            return;
        if (next.tdp_enabled && nativeTdpEnabled() !== false) {
            controls.dropTdp();
            next = await setTdpMode(false);
            next.warning = "Steam ha retomado el TDP; CPU y SMT siguen disponibles.";
            acquiredNativeTdp = false;
        }
        else if (next.tdp_enabled) {
            acquiredNativeTdp = true;
        }
        else if (acquiredNativeTdp && !next.desktop_busy && next.competitors.length === 0) {
            // A worker exit or mode handoff must not leave native Steam TDP disabled.
            await setNativeTdp(true);
            acquiredNativeTdp = false;
        }
        controls.publish(next);
    }
    catch (error) {
        controls.publish(null, String(error));
    }
    finally {
        reading = false;
    }
}
const Note = ({ children, warning = false }) => (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("div", { style: { fontSize: 12, lineHeight: 1.5, marginBottom: 12,
            padding: "10px 12px", borderRadius: 6, background: warning ? "#503a21" : "#23303d",
            color: "#f3f5f7", overflowWrap: "anywhere" }, children: children }) }));
function Content() {
    const [state, setState] = SP_REACT.useState(null);
    const [config, setConfig] = SP_REACT.useState({ watts: 15, smt: true, cores: 8, threads: 16 });
    const configRef = SP_REACT.useRef(config);
    const [error, setError] = SP_REACT.useState("");
    const [steamOff, setSteamOff] = SP_REACT.useState(false);
    SP_REACT.useEffect(() => {
        const unsubscribe = controls.subscribe((next, failure) => {
            setError(failure);
            if (!next || controls.pending)
                return;
            setState(next);
            setSteamOff(next.tdp_enabled);
            const cpu = next.cpu_target ?? next.cpu;
            const current = { smt: cpu.smt, cores: cpu.cores, threads: cpu.threads,
                watts: Math.max(3, Math.min(Math.round(next.tdp_target ?? (next.limits.stapm || 15)), next.power.max_watts)) };
            configRef.current = current;
            setConfig(current);
        });
        void refresh();
        return unsubscribe;
    }, []);
    function editCPU(change) {
        const next = { ...configRef.current, ...change };
        configRef.current = next;
        setConfig(next);
        setError("");
        controls.enqueue({ kind: "cpu", config: { smt: next.smt, cores: next.cores, threads: next.threads } });
    }
    function editTDP(watts) {
        const next = { ...configRef.current, watts: Math.round(watts) };
        configRef.current = next;
        setConfig(next);
        setError("");
        controls.enqueue({ kind: "tdp", watts: next.watts });
    }
    function editMode(enabled) {
        setSteamOff(enabled);
        setError("");
        controls.enqueue({ kind: "mode", enabled });
    }
    if (!state)
        return SP_JSX.jsx(DFL.PanelSection, { title: "Ally Power", children: SP_JSX.jsx(Note, { children: error || "Leyendo el estado de tu Ally…" }) });
    const blocked = !state.host.supported || !state.gaming || state.desktop_busy || state.competitors.length > 0;
    const maxThreads = config.smt ? Math.min(state.cpu.max_threads, config.cores * 2) : config.cores;
    const title = state.active ? "Control activo" : blocked ? "Control no disponible" : "Control en tiempo real";
    return SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsxs(DFL.PanelSection, { title: title, children: [SP_JSX.jsxs(Note, { children: [SP_JSX.jsx("strong", { children: state.power.ac ? "Con cargador" : "Batería" }), state.power.battery !== null ? ` · ${state.power.battery}%` : "", state.temperature !== null ? ` · ${state.temperature} °C` : "", SP_JSX.jsx("br", {}), "TDP configurado: ", SP_JSX.jsxs("strong", { children: [state.limits.stapm || "—", " W"] }), SP_JSX.jsx("br", {}), "CPU: ", state.cpu.cores, " n\u00FAcleos \u00B7 ", state.cpu.threads, " hilos \u00B7 SMT ", state.cpu.smt ? "activado" : "desactivado"] }), !state.host.supported && SP_JSX.jsx(Note, { warning: true, children: state.host.reason }), !state.gaming && SP_JSX.jsx(Note, { children: "Modo escritorio: utiliza Ally Power de escritorio. El plugin no cambia ajustes aqu\u00ED." }), state.desktop_busy && SP_JSX.jsx(Note, { warning: true, children: "Ally Power de escritorio tiene el control. Ci\u00E9rralo con \u00ABCerrar y conservar\u00BB." }), state.competitors.length > 0 && SP_JSX.jsxs(Note, { warning: true, children: ["Gestor activo: ", SP_JSX.jsx("strong", { children: state.competitors.join(", ") }), ".", SP_JSX.jsx("br", {}), "Desact\u00EDvalo en sus ajustes antes de usar estos controles. Ocultarlo no lo detiene."] }), (error || state.error || state.warning) && SP_JSX.jsx(Note, { warning: true, children: error || state.error || state.warning })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Ajuste manual", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "TDP de Steam desactivado", checked: steamOff, disabled: blocked || !nativeTdpAvailable(), description: steamOff ? "TDP controlado por el plugin. Al apagarlo vuelve a Steam." : "TDP nativo de Steam. SMT, núcleos e hilos siguen disponibles.", onChange: editMode }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "TDP", value: config.watts, min: 3, max: state.power.max_watts, step: 1, showValue: true, valueSuffix: " W", disabled: blocked || !steamOff, onChange: editTDP }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "SMT", checked: config.smt, disabled: blocked, description: "Independiente del control TDP. Los cambios se aplican autom\u00E1ticamente.", onChange: smt => editCPU({ smt, threads: smt ? Math.min(state.cpu.max_threads, configRef.current.cores * 2) : configRef.current.cores }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "N\u00FAcleos activos", value: config.cores, min: 1, max: state.cpu.max_cores, step: 1, showValue: true, disabled: blocked, onChange: value => {
                                const cores = Math.round(value), current = configRef.current;
                                editCPU({ cores, threads: current.smt ? Math.max(cores, Math.min(current.threads, cores * 2)) : cores });
                            } }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Hilos activos", value: config.threads, min: config.cores, max: Math.max(config.cores + 1, maxThreads), step: 1, showValue: true, disabled: blocked || maxThreads === config.cores, onChange: value => editCPU({ threads: Math.min(maxThreads, Math.round(value)) }) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Ajustes autom\u00E1ticos al mover los controles", children: [SP_JSX.jsxs(Note, { children: ["Sin botones de aplicar o liberar.", SP_JSX.jsx("br", {}), "3\u201325 W en bater\u00EDa \u00B7 3\u201330 W con cargador. Al salir de Gaming se conserva el estado y se cede el control."] }), !nativeTdpAvailable() && SP_JSX.jsx(Note, { warning: true, children: "No se ha detectado la API TDP de esta versi\u00F3n de Steam. Los controles de CPU no dependen de ella." }), SP_JSX.jsx(Note, { children: state.tdp_note })] })] });
}
var index = definePlugin(() => {
    const timer = setInterval(() => void refresh(), 2000);
    return {
        name: "Ally Power", titleView: SP_JSX.jsx("div", { className: DFL.staticClasses.Title, children: "Ally Power" }), content: SP_JSX.jsx(Content, {}),
        icon: SP_JSX.jsxs("svg", { viewBox: "0 0 24 24", fill: "none", width: "20", height: "20", "aria-hidden": "true", children: [SP_JSX.jsx("path", { d: "M7 6h10l4 11c.5 2-2 3-3 1l-2-3H8l-2 3c-1 2-3.5 1-3-1L7 6Z", stroke: "currentColor", strokeWidth: "1.8" }), SP_JSX.jsx("path", { d: "M7 9v4m-2-2h4m7-1h.1m2 2h.1M12 8l-1 3h2l-1 3", stroke: "currentColor", strokeWidth: "1.8", strokeLinecap: "round" })] }),
        onDismount() {
            clearInterval(timer);
            controls.stop();
            if (acquiredNativeTdp) {
                void setTdpMode(false).then(next => {
                    if (!next.error)
                        return setNativeTdp(true);
                }).catch(() => { });
            }
        },
    };
});

export { index as default };
//# sourceMappingURL=index.js.map
