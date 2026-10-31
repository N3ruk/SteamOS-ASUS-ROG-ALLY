const manifest = {"name":"Video Output ALLY for DOCKs"};
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

const getState = callable('get_state');
const selectOutput = callable('switch_connector');
function Outputs() {
    const [state, setState] = SP_REACT.useState(null);
    const [pending, setPending] = SP_REACT.useState(false);
    const [error, setError] = SP_REACT.useState('');
    const [loadingError, setLoadingError] = SP_REACT.useState('');
    SP_REACT.useEffect(() => {
        let active = true;
        let timer;
        const refresh = async () => {
            try {
                const value = await getState();
                if (active) {
                    setState(value);
                    setLoadingError('');
                }
            }
            catch {
                if (active)
                    setLoadingError('No se pudo consultar las pantallas.');
            }
            finally {
                if (active)
                    timer = setTimeout(refresh, 2000);
            }
        };
        void refresh();
        return () => { active = false; clearTimeout(timer); };
    }, []);
    const choose = async (id) => {
        if (pending)
            return;
        setPending(true);
        setError('');
        try {
            const result = await selectOutput(id);
            if (!result.ok)
                setError(result.error || 'No se pudo cambiar la pantalla.');
        }
        catch {
            setError('No se pudo comunicar con el controlador de vídeo.');
        }
        finally {
            setPending(false);
        }
    };
    const outputs = state?.connectors.filter(n => n.connected && !n.hidden) ?? [];
    const gaming = !!state?.video?.gaming;
    return (SP_JSX.jsxs(DFL.PanelSection, { title: "Salida de v\u00EDdeo", spinner: !state && !loadingError, children: [!gaming && state && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("div", { style: { fontSize: 12, opacity: .75 }, children: "Selecciona la pantalla desde el modo Gaming." }) }), state && !outputs.length && SP_JSX.jsx(DFL.PanelSectionRow, { children: "No hay pantallas conectadas." }), outputs.map(output => (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", label: output.enabled ? 'Activa' : undefined, description: !output.verified ? 'Identificación del monitor no disponible' : undefined, disabled: pending || !!state?.video?.busy || !gaming || !output.verified, onClick: () => { void choose(output.id); }, children: output.label }) }, output.id))), pending && SP_JSX.jsx(DFL.PanelSectionRow, { children: "Cambiando pantalla\u2026" }), (loadingError || error || state?.video?.error) && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("div", { role: "alert", style: { fontSize: 12, color: '#ffb6b6', overflowWrap: 'anywhere' }, children: loadingError || error || state?.video?.error }) })] }));
}
const MonitorIcon = () => SP_JSX.jsxs("svg", { width: "1em", height: "1em", "aria-hidden": "true", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.8", children: [SP_JSX.jsx("rect", { x: "2.5", y: "3.5", width: "19", height: "13", rx: "2" }), SP_JSX.jsx("path", { d: "M12 16.5v4M7.5 20.5h9" })] });
var index = definePlugin(() => ({
    name: 'Video Output ALLY for DOCKs',
    titleView: SP_JSX.jsx("div", { style: { fontSize: 15 }, children: "Video Output ALLY for DOCKs" }),
    content: SP_JSX.jsx(Outputs, {}),
    icon: SP_JSX.jsx(MonitorIcon, {}),
}));

export { index as default };
//# sourceMappingURL=index.js.map
