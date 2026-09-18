import { createIntl, createIntlCache } from "react-intl";
import { describe, expect, it } from "vitest";

import { SOURCE_MESSAGES } from "@/i18n/source";
import type { PersonaPoolCatalog } from "../types";
import {
  classifyPersonaPoolSampleError,
  personaPoolEmptyState,
  poolSlugLabel,
} from "../personaPoolCopy";

describe("persona-pool presentation state", () => {
  it("preserves a backend coverage error and exposes a stable UI code", () => {
    const raw =
      "Incomplete stratify coverage: 'life_stage=Early career' has 0, need sample_size_per_value_group=1.";

    expect(classifyPersonaPoolSampleError(raw)).toEqual({
      code: "persona_pool_coverage",
      rawMessage: raw,
      showRecoveryHint: true,
    });
  });

  it("maps internal pool ids to business display names", () => {
    const state = personaPoolEmptyState({
      pool: "persona/datasets/matraix-persona-dev-sample",
    } as PersonaPoolCatalog);
    const intl = createIntl(
      { locale: "en-US", messages: SOURCE_MESSAGES },
      createIntlCache(),
    );

    expect(state).toEqual({
      code: "persona_pool_empty",
      pool: "Amazon 买家 200",
    });
    expect(
      intl.formatMessage(
        { id: "catalog.personaStore.emptyPool" },
        { pool: state.pool },
      ),
    ).toBe("Amazon 买家 200 is empty or could not be loaded.");
    expect(poolSlugLabel("persona/datasets/validation-subset")).toBe("validation subset");
  });
});
