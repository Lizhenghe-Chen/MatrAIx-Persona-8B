// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

/**
 * 宿主嵌入探测：模块在加载时读取 `?embed=`，所以每个用例都用 resetModules + 动态 import
 * 拿到一份按当前地址求值的实例。
 */
async function loadEmbedModule(search: string) {
  window.history.replaceState({}, "", search);
  vi.resetModules();
  return await import("../embedMode");
}

describe("embed host detection", () => {
  it("treats a missing param as standalone", async () => {
    const embed = await loadEmbedModule("/");

    expect(embed.IS_EMBEDDED).toBe(false);
    expect(embed.EMBED_HOST).toBeNull();
    expect(embed.EMBED_LOCALE).toBeNull();
  });

  it("honours the host marker and its locale", async () => {
    const embed = await loadEmbedModule("/?mode=playground&embed=aifa");

    expect(embed.IS_EMBEDDED).toBe(true);
    expect(embed.EMBED_HOST).toBe("aifa");
    expect(embed.EMBED_LOCALE).toBe("zh-Hans");
    expect(document.documentElement.dataset.embed).toBe("aifa");
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });

  it("ignores unknown hosts so the standalone shell stays intact", async () => {
    const embed = await loadEmbedModule("/?embed=someone-else");

    expect(embed.IS_EMBEDDED).toBe(false);
  });
});

describe("brandNeutral", () => {
  it("keeps copy untouched when standalone", async () => {
    const embed = await loadEmbedModule("/");

    expect(embed.brandNeutral("MatrAIx · Runs")).toBe("MatrAIx · Runs");
  });

  it("strips the product brand from every known copy shape when embedded", async () => {
    const embed = await loadEmbedModule("/?embed=aifa");

    expect(embed.brandNeutral("MatrAIx · Runs")).toBe("Runs");
    expect(embed.brandNeutral("MatrAIx · 数字人世界")).toBe("数字人世界");
    expect(embed.brandNeutral("MatrAIx | Confidential evaluation report")).toBe(
      "Confidential evaluation report",
    );
    expect(embed.brandNeutral("In-process Matraix Playground runner")).toBe(
      "In-process runner",
    );
  });
});
