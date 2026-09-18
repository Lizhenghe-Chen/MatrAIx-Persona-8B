import {
  RawIntlProvider,
  createIntl,
  createIntlCache,
  type IntlShape,
} from "react-intl";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { createLatestRequestGuard, loadRegisteredLocale } from "./loader";
import { getLocaleDefinition, isUiLocale, type UiLocale } from "./registry";
import { SOURCE_LOCALE, SOURCE_MESSAGES, withEnglishFallback } from "./source";
import { brandNeutral, EMBED_LOCALE, IS_EMBEDDED } from "@/lib/embedMode";
import type {
  MessageCatalog,
  MessageKey,
  MessageValues,
  RichMessageValues,
} from "./types";

const STORAGE_KEY = "matraix.uiLocale";
const intlCache = createIntlCache();

export interface I18nContextValue {
  locale: UiLocale;
  loadingLocale: UiLocale | null;
  loadError: string | null;
  setLocale: (locale: UiLocale) => Promise<void>;
  t: (key: MessageKey, values?: MessageValues) => string;
  rich: (key: MessageKey, values?: RichMessageValues) => ReactNode;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function readStoredLocale(): UiLocale | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isUiLocale(stored) ? stored : null;
  } catch {
    return null;
  }
}

function persistLocale(locale: UiLocale): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // Storage may be disabled. The in-memory selection still works.
  }
}

export function syncDocumentLocale(locale: UiLocale): void {
  if (typeof document === "undefined") return;
  const definition = getLocaleDefinition(locale);
  document.documentElement.lang = definition.code;
  document.documentElement.dir = definition.dir;
}

function makeIntl(locale: UiLocale, messages: MessageCatalog): IntlShape {
  return createIntl(
    {
      locale,
      defaultLocale: SOURCE_LOCALE,
      messages: withEnglishFallback(scrubBrand(messages)),
      onError: (error) => {
        if (import.meta.env.DEV) console.error(error);
      },
    },
    intlCache,
  );
}

/** 嵌入宿主时不出现本产品品牌（只清洗展示文案，键名不变）。 */
function scrubBrand(catalog: MessageCatalog): MessageCatalog {
  if (!IS_EMBEDDED) return catalog;
  return Object.fromEntries(
    Object.entries(catalog).map(([key, text]) => [key, brandNeutral(text)]),
  ) as MessageCatalog;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setActiveLocale] = useState<UiLocale>(SOURCE_LOCALE);
  const [messages, setMessages] = useState<MessageCatalog>(SOURCE_MESSAGES);
  const [loadingLocale, setLoadingLocale] = useState<UiLocale | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const requestGuard = useRef(createLatestRequestGuard());

  const setLocale = useCallback(async (nextLocale: UiLocale) => {
    const requestId = requestGuard.current.begin();
    setLoadError(null);
    setLoadingLocale(nextLocale);
    try {
      const nextMessages = await loadRegisteredLocale(nextLocale);
      if (!requestGuard.current.isCurrent(requestId)) return;
      setMessages(nextMessages);
      setActiveLocale(nextLocale);
      persistLocale(nextLocale);
    } catch (error) {
      if (!requestGuard.current.isCurrent(requestId)) return;
      setLoadError(error instanceof Error ? error.message : String(error));
    } finally {
      if (requestGuard.current.isCurrent(requestId)) setLoadingLocale(null);
    }
  }, []);

  useEffect(() => {
    // 宿主嵌入时默认跟随宿主的界面语言（宿主为中文控制台）。
    const storedLocale = readStoredLocale() ?? EMBED_LOCALE ?? SOURCE_LOCALE;
    if (storedLocale !== SOURCE_LOCALE) void setLocale(storedLocale);
  }, [setLocale]);

  useEffect(() => syncDocumentLocale(locale), [locale]);

  const intl = useMemo(() => makeIntl(locale, messages), [locale, messages]);
  const t = useCallback<I18nContextValue["t"]>(
    (key, values) =>
      intl.formatMessage(
        { id: key, defaultMessage: brandNeutral(SOURCE_MESSAGES[key]) },
        values,
      ) as string,
    [intl],
  );
  const rich = useCallback<I18nContextValue["rich"]>(
    (key, values) =>
      intl.formatMessage(
        { id: key, defaultMessage: brandNeutral(SOURCE_MESSAGES[key]) },
        values,
      ) as ReactNode,
    [intl],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, loadingLocale, loadError, setLocale, t, rich }),
    [loadError, loadingLocale, locale, rich, setLocale, t],
  );

  return (
    <RawIntlProvider value={intl}>
      <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
    </RawIntlProvider>
  );
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}
