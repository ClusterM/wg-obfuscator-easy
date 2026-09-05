import { AxiosHeaderValue } from "axios";

export const isJsonResponse = (contentType: AxiosHeaderValue | undefined): boolean => (
  Array.isArray(contentType) ? contentType : [contentType]
).some(
  (value) =>
    typeof value === "string" &&
    value.includes("application/json"),
);