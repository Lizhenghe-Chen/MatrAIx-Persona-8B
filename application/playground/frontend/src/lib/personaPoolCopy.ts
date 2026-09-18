import type { PersonaPoolCatalog } from "./types";

/**
 * 展示名覆盖：pool 路径是数据层标识（磁盘目录、API 参数、缓存键都靠它），
 * 界面上只出现业务名，不出现内部代号。
 */
const POOL_DISPLAY_NAMES: Record<string, string> = {
  "matraix-persona-dev-sample": "Amazon 买家 200",
  "matraix-persona-1m": "amazon百万买家",
};

export function poolSlugLabel(poolPath: string): string {
  const slug = poolPath.split("/").filter(Boolean).pop() ?? poolPath;
  return POOL_DISPLAY_NAMES[slug] ?? slug.replace(/-/g, " ");
}

export interface PersonaPoolEmptyState {
  code: "persona_pool_empty";
  /** A dataset identifier to interpolate without translating it. */
  pool: string | null;
}

export function personaPoolEmptyState(
  catalog: PersonaPoolCatalog | null | undefined,
): PersonaPoolEmptyState {
  return {
    code: "persona_pool_empty",
    pool: catalog?.pool ? poolSlugLabel(catalog.pool) : null,
  };
}

/** Backend / sampling errors that mean the fixture pool is too thin for filters. */
export function isPersonaPoolCoverageError(message: string | null | undefined): boolean {
  const text = message ?? "";
  return (
    text.includes("exceeds matched pool size") ||
    text.includes("No personas with stratify fields") ||
    text.includes("sample_size_per_value_group=") ||
    text.includes("Incomplete stratify coverage") ||
    text.includes("matraix-persona-1m") ||
    text.includes("matraix-persona-dev-sample")
  );
}

export interface PersonaPoolSampleError {
  /** Known UI state; `rawMessage` remains unchanged for backend diagnostics. */
  code: "persona_pool_coverage" | null;
  rawMessage: string;
  /** Whether the rendering layer should add its localized recovery guidance. */
  showRecoveryHint: boolean;
}

/**
 * Classify a sampling failure without rewriting its backend / model text.
 * Components translate only the stable code and leave `rawMessage` intact.
 */
export function classifyPersonaPoolSampleError(
  message: string,
): PersonaPoolSampleError {
  const code = isPersonaPoolCoverageError(message)
    ? "persona_pool_coverage"
    : null;
  const alreadyHinted =
    message.includes("matraix-persona-1m") ||
    message.includes("Synthesize to fill") ||
    message.includes("does not synthesize");

  return {
    code,
    rawMessage: message,
    showRecoveryHint: code === "persona_pool_coverage" && !alreadyHinted,
  };
}
