export const zones = [
  { data: 'all', label: 'Todas las zonas', indexes: [0, 1, 2, 3] },
  { data: 'pair12', label: 'Zonas 1 y 2', indexes: [0, 1] },
  { data: 'pair34', label: 'Zonas 3 y 4', indexes: [2, 3] },
  { data: 'zone1', label: 'Zona 1', indexes: [0] },
  { data: 'zone2', label: 'Zona 2', indexes: [1] },
  { data: 'zone3', label: 'Zona 3', indexes: [2] },
  { data: 'zone4', label: 'Zona 4', indexes: [3] },
] as const;
export type Zone = typeof zones[number]['data'];
export type ZoneConfig = { effect: string; speed: number; color: string; transition_colors: string[] };
export type Config = { enabled: boolean; brightness: number; resume: boolean; zone: Zone; zones: ZoneConfig[] };
export const initial: Config = {
  enabled: true, brightness: 50, resume: true, zone: 'all',
  zones: Array.from({length:4}, () => ({effect:'solid', speed:50, color:'#00ddbb', transition_colors:['#00ddbb','#a43aff']})),
};
export function indexes(zone: Zone): readonly number[] {
  return zones.find(option => option.data === zone)!.indexes;
}
export function channelValue(hex: string, shift: number) {
  return (parseInt(hex.slice(1), 16) >> shift) & 255;
}
function channelHex(hex: string, shift: number, value: number) {
  const color = (parseInt(hex.slice(1), 16) & ~(255 << shift)) | (Math.round(value) << shift);
  return '#' + color.toString(16).padStart(6, '0');
}
function mapSelected(config: Config, change: (zone: ZoneConfig) => ZoneConfig): Partial<Config> {
  const selected = indexes(config.zone);
  return {zones:config.zones.map((zone, i) => selected.includes(i) ? change(zone) : zone)};
}
export function zoneSettings(config: Config, change: Partial<ZoneConfig>): Partial<Config> {
  return mapSelected(config, zone=>({...zone,...change}));
}
export function zoneChannel(config: Config, shift: number, value: number): Partial<Config> {
  return mapSelected(config, zone=>({...zone,color:channelHex(zone.color,shift,value)}));
}
export function transitionChannel(config: Config, endpoint: number, shift: number, value: number): Partial<Config> {
  return mapSelected(config, zone=>({...zone,transition_colors:zone.transition_colors.map((c,i)=>i===endpoint?channelHex(c,shift,value):c)}));
}
