import type { User } from "./api";

export function isPageHidden(user: User | null | undefined, page: string) {
  if (!user) return false;
  if (Array.isArray(user.paginas_liberadas)) {
    return !user.paginas_liberadas.includes(page);
  }
  return (user.paginas_ocultas ?? []).includes(page);
}

export function isResourceHidden(user: User | null | undefined, resource: string) {
  if (!user) return false;
  if (Array.isArray(user.recursos_liberados)) {
    return !user.recursos_liberados.includes(resource);
  }
  return (user.recursos_ocultos ?? []).includes(resource);
}
