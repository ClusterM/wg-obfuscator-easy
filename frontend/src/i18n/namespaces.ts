import type { Ns, NsUnion } from "./nsMap";

/**
 * Default namespace.
 */
export const defaultNS: NsUnion = "common";

/**
 * Default namespace type.
 */
export type DefaultNS = typeof defaultNS;

/**
 * All available namespaces.
 *
 * Edit this list manually every time you add/remove namespace in locales directory
 */
export const ns: Ns = ["common"];