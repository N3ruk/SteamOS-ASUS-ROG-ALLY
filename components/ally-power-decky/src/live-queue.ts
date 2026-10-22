export type CPUConfig = { smt: boolean; cores: number; threads: number };
export type Command = { kind: "cpu"; config: CPUConfig } | { kind: "tdp"; watts: number } | { kind: "mode"; enabled: boolean };

/** Serialize hardware transactions and coalesce slider repeats to the latest value. */
export class LiveQueue<T> {
  private queue: Command[] = [];
  private running = false;
  private stopped = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private listeners = new Set<(result: T | null, error: string) => void>();
  private execute: (command: Command) => Promise<T>;
  constructor(execute: (command: Command) => Promise<T>) { this.execute = execute; }
  get pending() { return this.running || this.queue.length > 0; }
  subscribe(fn: (result: T | null, error: string) => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; }
  publish(result: T | null, error = "") { for (const fn of this.listeners) fn(result, error); }
  dropTdp() { this.queue = this.queue.filter(c => c.kind !== "tdp"); }
  enqueue(command: Command) {
    if (this.stopped) return;
    this.queue = this.queue.filter(c => c.kind !== command.kind);
    if (command.kind === "mode") {
      if (!command.enabled) this.dropTdp();
      this.queue.unshift(command);
    } else this.queue.push(command);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.timer = null; void this.flush(); }, command.kind === "mode" ? 0 : 120);
  }
  async flush() {
    if (this.running || this.stopped) return;
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    this.running = true;
    let result: T | null = null;
    let error = "";
    try {
      while (this.queue.length && !this.stopped) {
        const command = this.queue.shift()!;
        try { result = await this.execute(command); error = ""; }
        catch (e) {
          error = String(e);
          if (command.kind === "mode") this.dropTdp();
        }
      }
    } finally {
      this.running = false;
      if (!this.stopped) this.publish(result, error);
    }
  }
  stop() {
    this.stopped = true; this.queue = [];
    if (this.timer) clearTimeout(this.timer);
    this.listeners.clear();
  }
}
