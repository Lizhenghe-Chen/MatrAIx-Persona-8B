import type { ReactNode } from "react";

export interface CockpitSetupShellProps {
  header: ReactNode;
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

/**
 * Full-viewport three-column cockpit — side rails scroll internally; no page scroll.
 *
 * < xl：三栏改为堆叠 —— 两条侧栏并排在上（选择数字人/任务），中央流水线整行在下。
 * 这样每栏都能拿到足够宽度（不再被均分成 1/3 视口高而裁掉内容），外层栅格自身可滚动，
 * 页面本身仍不滚动。视觉顺序与 DOM 顺序不同（中央栏用 order/col-span 调整）。
 */
export function CockpitSetupShell({ header, left, center, right }: CockpitSetupShellProps) {
  return (
    <div className="cockpit-mesh-bg flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-outline/30 bg-surface-lowest/70 px-5 py-2 backdrop-blur-md">
        {header}
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto px-3 py-2.5 sm:grid-cols-2 xl:grid-cols-12 xl:gap-4 xl:overflow-hidden xl:px-5 xl:py-3">
        <div className="order-1 flex h-[520px] flex-col overflow-hidden xl:order-none xl:col-span-3 xl:h-full xl:min-h-0">
          {left}
        </div>
        <div className="order-3 flex h-[440px] flex-col overflow-hidden sm:col-span-2 xl:order-none xl:col-span-6 xl:h-full xl:min-h-0">
          {center}
        </div>
        <div className="order-2 flex h-[520px] flex-col overflow-hidden xl:order-none xl:col-span-3 xl:h-full xl:min-h-0">
          {right}
        </div>
      </div>
    </div>
  );
}
