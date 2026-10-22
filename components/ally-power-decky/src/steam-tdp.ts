import { findModuleChild } from "@decky/ui";
type Setter = (key: string, value: boolean) => Promise<unknown> | unknown;
let setter: Setter | undefined;
function store(): { clientSettings?: Record<string, unknown> } | undefined {
  return (globalThis as unknown as { settingsStore?: { clientSettings?: Record<string, unknown> } }).settingsStore;
}
/** Reuse the exact settings setter used by Steam's native performance UI. */
function resolveSetter(): Setter | undefined {
  if (setter) return setter;
  const settings = store();
  if (!settings) return undefined;
  setter = findModuleChild((module: unknown) => {
    if (!module || typeof module !== "object") return;
    const values = Object.values(module);
    if (!values.includes(settings)) return;
    return values.find(value => typeof value === "function" &&
      Function.prototype.toString.call(value).includes("SteamClient.Settings.SetSetting"));
  }) as Setter | undefined;
  return setter;
}
export function nativeTdpEnabled(): boolean | null {
  const value = store()?.clientSettings?.steamos_tdp_limit_enabled;
  return typeof value === "boolean" ? value : null;
}
export function nativeTdpAvailable(): boolean { return nativeTdpEnabled() !== null && !!resolveSetter(); }
export async function setNativeTdp(enabled: boolean): Promise<void> {
  const update = resolveSetter();
  if (!update || nativeTdpEnabled() === null) throw new Error("Esta versión de Steam no expone su control TDP. Los controles de CPU siguen disponibles.");
  if (nativeTdpEnabled() === enabled) return;
  await update("steamos_tdp_limit_enabled", enabled);
  for (let i = 0; i < 50; i++) {
    if (nativeTdpEnabled() === enabled) return;
    await new Promise(resolve => setTimeout(resolve, 40));
  }
  throw new Error("Steam no confirmó el cambio de su control TDP.");
}
