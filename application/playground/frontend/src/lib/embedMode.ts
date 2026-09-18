/**
 * 嵌入模式（宿主：AIFA Claw）。
 *
 * 宿主用 iframe 挂载本 SPA，并在地址上带 `?embed=aifa`：
 * - 外壳精简：不渲染本产品字标与落地页（见 TopBar / App），配色与圆角切到宿主（见 aifaEmbed.css）；
 * - 文案不出现本产品品牌（见 i18n/I18nProvider 的 brandNeutral 清洗）；
 * - 独立访问（无该参数）行为完全不变。
 *
 * 参数由宿主写在 iframe 地址上，且本 SPA 的自身跳转（lib/useUrlState.ts）只增删自己的
 * query key，不会丢掉它。
 */
const PARAM = "embed";

/** 支持的宿主；label 用于浏览器标签页标题，locale 为首次进入时的默认界面语言。 */
const HOSTS = {
  aifa: { label: "AIFA Claw", locale: "zh-Hans" },
} as const;

export type EmbedHost = keyof typeof HOSTS;

function readHost(): EmbedHost | null {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get(PARAM);
  return raw && raw in HOSTS ? (raw as EmbedHost) : null;
}

/** 宿主标识；独立访问为 null。 */
export const EMBED_HOST: EmbedHost | null = readHost();
export const IS_EMBEDDED = EMBED_HOST !== null;

/** 宿主配套的默认界面语言（宿主为中文控制台）。 */
export const EMBED_LOCALE = EMBED_HOST ? HOSTS[EMBED_HOST].locale : null;

if (EMBED_HOST) {
  const root = document.documentElement;
  root.dataset.embed = EMBED_HOST;
  // 宿主是浅色控制台：嵌入时锁定浅色（TopBar 在嵌入时不渲染主题切换按钮）。
  root.classList.add("light");
  root.classList.remove("dark");
  document.title = HOSTS[EMBED_HOST].label;
}

/**
 * 去掉展示文案里的本产品品牌，只留功能描述（嵌入时使用）。
 * 覆盖两种写法：`MatrAIx · Persona World` 这类 eyebrow，以及 `MatrAIx Playground` 这类前缀。
 */
export function brandNeutral(text: string): string {
  if (!EMBED_HOST) return text;
  return text
    .replace(/\s*(?:MatrAIx|Matraix)\s*(?:Playground)?\s*[·|]?\s*/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
}
