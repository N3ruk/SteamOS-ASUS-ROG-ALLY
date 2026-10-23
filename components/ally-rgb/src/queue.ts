/** Latest complete frame wins; one backend operation at a time. */
export class LatestQueue<T, R> {
  private next: T | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running: Promise<void> | null = null;
  private closed = false;
  onResult: (result: R | null, error: string, pending: boolean) => void = () => {};
  constructor(private execute: (value: T) => Promise<R>, private delay = 100) {}
  get pending() { return this.next !== null || this.timer !== null || this.running !== null; }
  enqueue(value: T) {
    if (this.closed) return;
    this.next = value;
    this.onResult(null, "", true);
    if (!this.running && !this.timer) this.timer = setTimeout(() => {
      this.timer = null; this.start();
    }, this.delay);
  }
  private start() {
    this.running = this.drain().finally(() => {
      this.running = null;
      this.onResult(null, "", this.pending);
      if (this.next !== null && !this.closed) this.start();
    });
  }
  private async drain() {
    while (this.next !== null && !this.closed) {
      const value = this.next;
      this.next = null;
      try { const result = await this.execute(value); this.onResult(result, "", this.next !== null); }
      catch (error) { this.onResult(null, String(error), this.next !== null); }
    }
  }
  drop() {
    this.next = null;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }
  async idle() {
    while (this.running || this.timer) {
      if (this.running) await this.running;
      else await new Promise(resolve => setTimeout(resolve, 10));
    }
  }
  async close() { this.closed = true; this.drop(); await this.idle(); }
}
