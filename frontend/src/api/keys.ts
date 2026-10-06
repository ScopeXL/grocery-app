/** Every TanStack Query key in one place (docs/PLAN.md §9.4). */
export const qk = {
  session: () => ["session"] as const,
  members: () => ["members"] as const,
  settings: () => ["settings"] as const,
  devices: () => ["devices"] as const,
  diagnostics: () => ["diagnostics"] as const,
  backups: () => ["backups"] as const,
};
