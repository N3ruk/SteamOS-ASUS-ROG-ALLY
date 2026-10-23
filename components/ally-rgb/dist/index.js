const manifest = {"name":"ALLY RGB"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api$1;
try {
    api$1 = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api$1 = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api$1._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api$1._version}. Some features may not work.`);
}
const callable = api$1.callable;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

/** Latest complete frame wins; one backend operation at a time. */
class LatestQueue {
    constructor(execute, delay = 100) {
        this.execute = execute;
        this.delay = delay;
        this.next = null;
        this.timer = null;
        this.running = null;
        this.closed = false;
        this.onResult = () => { };
    }
    get pending() { return this.next !== null || this.timer !== null || this.running !== null; }
    enqueue(value) {
        if (this.closed)
            return;
        this.next = value;
        this.onResult(null, "", true);
        if (!this.running && !this.timer)
            this.timer = setTimeout(() => {
                this.timer = null;
                this.start();
            }, this.delay);
    }
    start() {
        this.running = this.drain().finally(() => {
            this.running = null;
            this.onResult(null, "", this.pending);
            if (this.next !== null && !this.closed)
                this.start();
        });
    }
    async drain() {
        while (this.next !== null && !this.closed) {
            const value = this.next;
            this.next = null;
            try {
                const result = await this.execute(value);
                this.onResult(result, "", this.next !== null);
            }
            catch (error) {
                this.onResult(null, String(error), this.next !== null);
            }
        }
    }
    drop() {
        this.next = null;
        if (this.timer)
            clearTimeout(this.timer);
        this.timer = null;
    }
    async idle() {
        while (this.running || this.timer) {
            if (this.running)
                await this.running;
            else
                await new Promise(resolve => setTimeout(resolve, 10));
        }
    }
    async close() { this.closed = true; this.drop(); await this.idle(); }
}

const zones = [
    { data: 'all', label: 'Todas las zonas', indexes: [0, 1, 2, 3] },
    { data: 'pair12', label: 'Zonas 1 y 2', indexes: [0, 1] },
    { data: 'pair34', label: 'Zonas 3 y 4', indexes: [2, 3] },
    { data: 'zone1', label: 'Zona 1', indexes: [0] },
    { data: 'zone2', label: 'Zona 2', indexes: [1] },
    { data: 'zone3', label: 'Zona 3', indexes: [2] },
    { data: 'zone4', label: 'Zona 4', indexes: [3] },
];
const initial = {
    enabled: true, brightness: 50, resume: true, zone: 'all',
    zones: Array.from({ length: 4 }, () => ({ effect: 'solid', speed: 50, color: '#00ddbb', transition_colors: ['#00ddbb', '#a43aff'] })),
};
function indexes(zone) {
    return zones.find(option => option.data === zone).indexes;
}
function channelValue(hex, shift) {
    return (parseInt(hex.slice(1), 16) >> shift) & 255;
}
function channelHex(hex, shift, value) {
    const color = (parseInt(hex.slice(1), 16) & ~(255 << shift)) | (Math.round(value) << shift);
    return '#' + color.toString(16).padStart(6, '0');
}
function mapSelected(config, change) {
    const selected = indexes(config.zone);
    return { zones: config.zones.map((zone, i) => selected.includes(i) ? change(zone) : zone) };
}
function zoneSettings(config, change) {
    return mapSelected(config, zone => ({ ...zone, ...change }));
}
function zoneChannel(config, shift, value) {
    return mapSelected(config, zone => ({ ...zone, color: channelHex(zone.color, shift, value) }));
}
function transitionChannel(config, endpoint, shift, value) {
    return mapSelected(config, zone => ({ ...zone, transition_colors: zone.transition_colors.map((c, i) => i === endpoint ? channelHex(c, shift, value) : c) }));
}

const api = {
    state: callable('get_state'), apply: callable('apply_config'),
    select: callable('select_zone'), pause: callable('pause'),
    resume: callable('resume'),
};
// Steam's Dropdown supports controlled mode, omitted from @decky/ui 4.12.1's types.
// Keep the displayed editor selection on the same source of truth as saved settings.
const ControlledDropdown = DFL.DropdownItem;
const effects = [['solid', 'Color fijo'], ['breath', 'Respiración'], ['rainbow', 'Arcoíris'], ['wave', 'Onda'], ['gradient', 'Transición'], ['battery', 'Batería']];
const zoneOptions = zones.map(({ data, label }) => ({ data, label }));
const channels = [[16, 'Rojo'], [8, 'Verde'], [0, 'Azul']];
const subscribers = new Set();
let current = null;
let lastError = '';
let reading = false;
let hooks = false;
let hooksWarning = '';
let closing = false;
let revision = 0;
let lightingRevision = 0;
let confirmedLightingRevision = 0;
let desired = null;
function publish(next, error = '', pending = false) {
    if (next)
        current = next;
    if (error || next)
        lastError = error || next?.error || '';
    if (!pending && !queue.pending && current)
        desired = fromState(current);
    for (const listener of subscribers)
        listener(next, lastError, pending);
}
const queue = new LatestQueue(async (request) => ({
    state: await (request.apply ? api.apply(request.config) : api.select(request.config.zone)), revision: request.revision,
}));
queue.onResult = (result, error, pending) => {
    if (result && !result.state.error)
        confirmedLightingRevision = Math.max(confirmedLightingRevision, result.revision);
    publish(result?.state || null, error, pending);
};
async function refresh() {
    if (reading || queue.pending || closing)
        return;
    reading = true;
    const observedRevision = revision;
    try {
        const state = await api.state();
        if (!queue.pending && observedRevision === revision)
            publish(state);
    }
    catch (error) {
        publish(null, String(error));
    }
    finally {
        reading = false;
    }
}
function fromState(state) {
    if (state.config)
        return { ...state.config, zone: state.editor_zone || state.config.zone };
    const actual = state.actual;
    return { ...initial, zone: state.editor_zone || 'all', zones: initial.zones.map((zone, i) => ({ ...zone,
            color: actual?.hex[i] || zone.color, transition_colors: [...zone.transition_colors] })),
        enabled: !!actual && actual.brightness > 0, brightness: actual ? Math.round(actual.brightness * 100 / 255) : 50 };
}
const Note = ({ children }) => SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("div", { style: { padding: 12, background: '#183035', borderRadius: 8, fontSize: 12, lineHeight: 1.55 }, children: children }) });
function Content() {
    const [state, setState] = SP_REACT.useState(current);
    const [config, setConfig] = SP_REACT.useState(desired || (current ? fromState(current) : initial));
    const draft = SP_REACT.useRef(config);
    const [error, setError] = SP_REACT.useState(lastError);
    const [pending, setPending] = SP_REACT.useState(queue.pending);
    SP_REACT.useEffect(() => {
        const listener = (next, failure, waiting) => {
            setPending(waiting);
            setError(failure);
            const confirmed = next || (!waiting && !queue.pending ? current : null);
            if (confirmed) {
                setState(confirmed);
                if (!waiting && !queue.pending) {
                    const value = fromState(confirmed);
                    draft.current = value;
                    setConfig(value);
                }
            }
        };
        subscribers.add(listener);
        void refresh();
        const poll = setInterval(() => void refresh(), 2000);
        return () => { subscribers.delete(listener); clearInterval(poll); };
    }, []);
    const blocked = !state?.supported || !!state?.conflicts.length;
    function edit(change, selectionOnly = false) {
        revision++;
        if (!selectionOnly)
            lightingRevision++;
        const next = { ...draft.current, ...change };
        desired = next;
        draft.current = next;
        setConfig(next);
        setError('');
        queue.enqueue({ config: next, apply: lightingRevision > confirmedLightingRevision, revision: lightingRevision });
    }
    if (!state)
        return SP_JSX.jsx(DFL.PanelSection, { title: "ALLY RGB", children: SP_JSX.jsx(Note, { children: error || 'Leyendo la iluminación de tu Ally…' }) });
    const selected = indexes(config.zone);
    const zoneConfig = config.zones[selected[0]];
    const effect = selected.every(i => config.zones[i].effect === zoneConfig.effect) ? zoneConfig.effect : 'mixed';
    const status = error || state.error || state.warning || hooksWarning ||
        (state.conflicts.length ? 'Desactiva el otro gestor RGB: ' + state.conflicts.join(', ') :
            state.paused ? 'Pausado durante la suspensión.' : state.active ? 'ALLY RGB tiene el control.' : 'Sin control adquirido.');
    const displayColors = state.active && state.actual ? state.actual.hex : config.zones.map(zone => zone.color);
    return SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSection, { children: SP_JSX.jsxs(Note, { children: [SP_JSX.jsx("strong", { children: "ALLY RGB" }), " \u00B7 4 zonas", state.battery !== null ? ` · batería ${state.battery}%` : ' · batería sin datos', SP_JSX.jsx("div", { style: { display: 'flex', gap: 12, padding: '12px 0' }, children: displayColors.map((c, i) => SP_JSX.jsx("div", { title: `Zona ${i + 1}: ${c}${selected.includes(i) ? ' · seleccionada' : ''}`, style: { background: c, color: '#fff', textShadow: '0 1px 3px #000', display: 'grid', placeItems: 'center', width: 38, height: 38, borderRadius: '50%', border: selected.includes(i) ? '3px solid #d1fff2' : '3px solid #556168', opacity: selected.includes(i) ? 1 : .55 }, children: i + 1 }, i)) }), SP_JSX.jsx("div", { children: pending ? 'Aplicando el último cambio…' : status })] }) }), SP_JSX.jsxs(DFL.PanelSection, { title: "Iluminaci\u00F3n", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Iluminaci\u00F3n", checked: config.enabled, disabled: blocked, onChange: enabled => edit({ enabled }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Brillo", value: config.brightness, min: 0, max: 100, step: 1, valueSuffix: "%", disabled: blocked, onChange: brightness => edit({ brightness: Math.round(brightness) }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(ControlledDropdown, { controlled: true, label: "Zonas", selectedOption: config.zone, rgOptions: zoneOptions, disabled: blocked, onChange: o => edit({ zone: o.data }, true) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(ControlledDropdown, { controlled: true, label: "Efecto", selectedOption: effect, rgOptions: [...(effect === 'mixed' ? [{ data: 'mixed', label: 'Varios efectos (conservar)' }] : []), ...effects.map(([data, label]) => ({ data, label }))], disabled: blocked, onChange: o => { if (o.data !== 'mixed')
                                edit(zoneSettings(draft.current, { effect: o.data })); } }) }), effect !== 'mixed' && effect !== 'solid' && effect !== 'battery' && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Velocidad", value: zoneConfig.speed, min: 10, max: 100, step: 1, valueSuffix: "%", disabled: blocked, onChange: speed => edit(zoneSettings(draft.current, { speed: Math.round(speed) })) }) })] }), (effect === 'solid' || effect === 'breath') && SP_JSX.jsx(DFL.PanelSection, { title: "Color de las zonas seleccionadas", children: channels.map(([shift, label]) => SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: label, value: channelValue(zoneConfig.color, shift), min: 0, max: 255, step: 1, disabled: blocked, onChange: value => edit(zoneChannel(draft.current, shift, value)) }) }, label)) }), effect === 'gradient' && zoneConfig.transition_colors.map((color, endpoint) => SP_JSX.jsxs(DFL.PanelSection, { title: endpoint === 0 ? 'Color inicial' : 'Color final', children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("div", { style: { height: 20, width: '100%', background: color, border: '1px solid #d1fff2', borderRadius: 4 } }) }), channels.map(([shift, label]) => SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: label, value: channelValue(color, shift), min: 0, max: 255, step: 1, disabled: blocked, onChange: value => edit(transitionChannel(draft.current, endpoint, shift, value)) }) }, label))] }, endpoint)), SP_JSX.jsx(DFL.PanelSection, { children: SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Recuperar al despertar/encender", checked: config.resume, disabled: blocked, description: hooks ? 'Guarda los ajustes y los restaura al despertar o encender.' : 'Restaura al encender; Steam no ofrece la señal de despertar en esta sesión.', onChange: resume => edit({ resume }) }) }) })] });
}
var index = definePlugin(() => {
    const registrations = [];
    const system = window.SteamClient?.System;
    let powerChain = Promise.resolve();
    try {
        if (system?.RegisterForOnSuspendRequest && system?.RegisterForOnResumeFromSuspend) {
            registrations.push(system.RegisterForOnSuspendRequest(() => {
                queue.drop();
                powerChain = powerChain.then(async () => { await queue.idle(); publish(await api.pause()); }).catch(e => publish(null, String(e)));
            }));
            registrations.push(system.RegisterForOnResumeFromSuspend(() => {
                powerChain = powerChain.then(async () => { publish(await api.resume()); }).catch(e => publish(null, String(e)));
            }));
            hooks = true;
        }
    }
    catch {
        hooksWarning = 'No se ha podido activar la recuperación automática al despertar.';
    }
    return { name: 'ALLY RGB', titleView: SP_JSX.jsx("div", { className: DFL.staticClasses.Title, children: "ALLY RGB" }),
        content: SP_JSX.jsx(Content, {}), icon: SP_JSX.jsx("span", { style: { color: '#7be5cd' }, children: "\u25C9" }),
        onDismount() {
            closing = true;
            for (const item of registrations) {
                if (typeof item === 'function')
                    item();
                else
                    item?.unregister?.();
            }
            // Backend lifecycle owns shutdown. A late frontend unload must not release
            // a freshly reloaded backend after it restored the user's saved settings.
            void queue.close().then(() => powerChain).catch(() => { });
        } };
});

export { index as default };
//# sourceMappingURL=index.js.map
