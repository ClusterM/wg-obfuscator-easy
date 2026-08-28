import "i18next";

import { DefaultNS } from "./namespaces";
import type { NsMap } from "./nsMap";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: DefaultNS;
    resources: NsMap;
  }
}