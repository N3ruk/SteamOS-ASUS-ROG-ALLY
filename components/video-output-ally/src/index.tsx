import { useEffect, useState } from 'react';
import { callable, definePlugin } from '@decky/api';
import { ButtonItem, PanelSection, PanelSectionRow } from '@decky/ui';

interface Connector {
  id: string;
  label: string;
  hidden: boolean;
  connected: boolean;
  enabled: boolean;
  verified: boolean;
}
interface VideoState {
  connectors: Connector[];
  video: { gaming: boolean; busy: boolean; error: string } | null;
}
interface Result { ok: boolean; error?: string }
const getState = callable<[], VideoState>('get_state');
const selectOutput = callable<[string], Result>('switch_connector');

function Outputs() {
  const [state, setState] = useState<VideoState | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [loadingError, setLoadingError] = useState('');
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const value = await getState();
        if (active) { setState(value); setLoadingError(''); }
      } catch {
        if (active) setLoadingError('No se pudo consultar las pantallas.');
      } finally {
        if (active) timer = setTimeout(refresh, 2000);
      }
    };
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, []);

  const choose = async (id: string) => {
    if (pending) return;
    setPending(true);
    setError('');
    try {
      const result = await selectOutput(id);
      if (!result.ok) setError(result.error || 'No se pudo cambiar la pantalla.');
    } catch {
      setError('No se pudo comunicar con el controlador de vídeo.');
    } finally {
      setPending(false);
    }
  };
  const outputs = state?.connectors.filter(n => n.connected && !n.hidden) ?? [];
  const gaming = !!state?.video?.gaming;
  return (
    <PanelSection title="Salida de vídeo" spinner={!state && !loadingError}>
      {!gaming && state && <PanelSectionRow>
        <div style={{ fontSize: 12, opacity: .75 }}>Selecciona la pantalla desde el modo Gaming.</div>
      </PanelSectionRow>}
      {state && !outputs.length && <PanelSectionRow>No hay pantallas conectadas.</PanelSectionRow>}
      {outputs.map(output => (
        <PanelSectionRow key={output.id}>
          <ButtonItem
            layout="below"
            label={output.enabled ? 'Activa' : undefined}
            description={!output.verified ? 'Identificación del monitor no disponible' : undefined}
            disabled={pending || !!state?.video?.busy || !gaming || !output.verified}
            onClick={() => { void choose(output.id); }}
          >{output.label}</ButtonItem>
        </PanelSectionRow>
      ))}
      {pending && <PanelSectionRow>Cambiando pantalla…</PanelSectionRow>}
      {(loadingError || error || state?.video?.error) && <PanelSectionRow>
        <div role="alert" style={{ fontSize: 12, color: '#ffb6b6', overflowWrap: 'anywhere' }}>
          {loadingError || error || state?.video?.error}
        </div>
      </PanelSectionRow>}
    </PanelSection>
  );
}

const MonitorIcon = () => <svg width="1em" height="1em" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
  <rect x="2.5" y="3.5" width="19" height="13" rx="2" />
  <path d="M12 16.5v4M7.5 20.5h9" />
</svg>;

export default definePlugin(() => ({
  name: 'Video Output ALLY for DOCKs',
  titleView: <div style={{ fontSize: 15 }}>Video Output ALLY for DOCKs</div>,
  content: <Outputs />,
  icon: <MonitorIcon />,
}));
