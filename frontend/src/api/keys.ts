/** Every TanStack Query key in one place (docs/PLAN.md §9.4). */
export const qk = {
  session: () => ["session"] as const,
  members: () => ["members"] as const,
  settings: () => ["settings"] as const,
  devices: () => ["devices"] as const,
  diagnostics: () => ["diagnostics"] as const,
  backups: () => ["backups"] as const,
  activeStore: () => ["stores", "active"] as const,
  dishes: () => ["dishes"] as const,
  dishList: (role: string, archived: boolean) => ["dishes", "list", role, archived] as const,
  dish: (id: string) => ["dishes", "one", id] as const,
  items: () => ["items"] as const,
  picker: (itemId: string) => ["items", "picker", itemId] as const,
  productSearch: (term: string) => ["products", term] as const,
};
