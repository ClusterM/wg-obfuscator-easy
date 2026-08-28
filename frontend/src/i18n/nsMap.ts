/*
 * Import all namespaces (for the default language, only)
 *
 * Edit this list manually every time you add/remove namespace in locales directory
 */
import common from "./locales/en/common.json";

/**
 * The namespace map used to define resource types in the i18next.d.ts file.
 *
 * Edit this list manually every time you add/remove namespace in locales directory
 */
export type NsMap = {
  common: typeof common;
};

/**
 * Union type of namespaces.
 */
export type NsUnion = keyof NsMap;

/**
 * An array type of all available namespaces.
 */
export type Ns = NsUnion[];