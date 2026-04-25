import * as RadixToast from "@radix-ui/react-toast";
import { AlertTriangle, CheckCircle, Info, X, XCircle } from "lucide-react";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { cn } from "../lib/utils";

export type ToastType = "success" | "error" | "warning" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  durationMs: number;
}

interface ToastContextValue {
  push: (type: ToastType, title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

// Auto-dismiss rules from docs/design.md §Toast
const DURATIONS: Record<ToastType, number> = {
  success: 4000,
  info: 4000,
  warning: 6000,
  error: 0, // manual only
};

const ICONS: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle className="h-4 w-4" aria-hidden />,
  error: <XCircle className="h-4 w-4" aria-hidden />,
  warning: <AlertTriangle className="h-4 w-4" aria-hidden />,
  info: <Info className="h-4 w-4" aria-hidden />,
};

const PALETTES: Record<ToastType, { bg: string; fg: string }> = {
  success: { bg: "bg-favorable-bg", fg: "text-favorable-fg" },
  error: { bg: "bg-severity-high-bg", fg: "text-severity-high-fg" },
  warning: { bg: "bg-severity-medium-bg", fg: "text-severity-medium-fg" },
  info: { bg: "bg-severity-normal-bg", fg: "text-severity-normal-fg" },
};

const ROLE: Record<ToastType, "status" | "alert"> = {
  success: "status",
  info: "status",
  warning: "alert",
  error: "alert",
};

const MAX_STACKED = 3;
const DEDUP_WINDOW_MS = 1000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const recentRef = useRef<Map<string, number>>(new Map());

  const push = useCallback(
    (type: ToastType, title: string, description?: string) => {
      // Dedup — identical text + type within 1s → skip
      const key = `${type}:${title}:${description ?? ""}`;
      const now = Date.now();
      const last = recentRef.current.get(key) ?? 0;
      if (now - last < DEDUP_WINDOW_MS) return;
      recentRef.current.set(key, now);

      const id = `${now}-${Math.random().toString(36).slice(2, 8)}`;
      const item: ToastItem = {
        id,
        type,
        title,
        description,
        durationMs: DURATIONS[type],
      };
      // Max 3 stacked — oldest dropped when the cap is hit
      setItems((prev) => [...prev, item].slice(-MAX_STACKED));
    },
    []
  );

  const remove = useCallback((id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  // Register globally so non-React callers (e.g. api.ts) can toast
  // without being inside a component tree.
  useEffect(() => {
    globalToast = {
      success: (t, d) => push("success", t, d),
      error: (t, d) => push("error", t, d),
      warning: (t, d) => push("warning", t, d),
      info: (t, d) => push("info", t, d),
    };
    return () => {
      globalToast = fallbackToast;
    };
  }, [push]);

  return (
    <ToastContext.Provider value={{ push }}>
      <RadixToast.Provider swipeDirection="right">
        {children}
        {items.map((t) => {
          const palette = PALETTES[t.type];
          return (
            <RadixToast.Root
              key={t.id}
              duration={t.durationMs === 0 ? Infinity : t.durationMs}
              onOpenChange={(open) => {
                if (!open) remove(t.id);
              }}
              role={ROLE[t.type]}
              className={cn(
                "toast-root pointer-events-auto rounded-md border border-border shadow-md p-3",
                "flex gap-3 items-start",
                palette.bg,
                palette.fg
              )}
            >
              <div className="mt-0.5">{ICONS[t.type]}</div>
              <div className="flex-1 min-w-0">
                <RadixToast.Title className="text-sm font-medium">
                  {t.title}
                </RadixToast.Title>
                {t.description && (
                  <RadixToast.Description className="text-sm opacity-90 mt-0.5">
                    {t.description}
                  </RadixToast.Description>
                )}
              </div>
              <RadixToast.Close
                aria-label="Dismiss"
                className="opacity-70 hover:opacity-100"
              >
                <X className="h-4 w-4" />
              </RadixToast.Close>
            </RadixToast.Root>
          );
        })}
        <RadixToast.Viewport
          className={cn(
            "fixed z-[100] flex flex-col gap-2",
            "top-4 right-4 w-[360px] max-w-[calc(100vw-2rem)]",
            "max-sm:left-4 max-sm:right-4 max-sm:w-auto"
          )}
        />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return {
    success: (title: string, description?: string) =>
      ctx.push("success", title, description),
    error: (title: string, description?: string) =>
      ctx.push("error", title, description),
    warning: (title: string, description?: string) =>
      ctx.push("warning", title, description),
    info: (title: string, description?: string) =>
      ctx.push("info", title, description),
  };
}

// ----- Global toast (for non-React callers like api.ts) -----
type ToastFn = (title: string, description?: string) => void;
interface GlobalToast {
  success: ToastFn;
  error: ToastFn;
  warning: ToastFn;
  info: ToastFn;
}

// Safe fallback used before ToastProvider mounts.
const fallbackToast: GlobalToast = {
  success: (t, d) => console.info("[toast:success]", t, d),
  error: (t, d) => console.error("[toast:error]", t, d),
  warning: (t, d) => console.warn("[toast:warning]", t, d),
  info: (t, d) => console.info("[toast:info]", t, d),
};

let globalToast: GlobalToast = fallbackToast;

/**
 * Non-hook toast — safe to call from anywhere. Before ToastProvider mounts,
 * messages go to the console; after mount, they render via Radix Toast.
 */
export const toast: GlobalToast = {
  success: (t, d) => globalToast.success(t, d),
  error: (t, d) => globalToast.error(t, d),
  warning: (t, d) => globalToast.warning(t, d),
  info: (t, d) => globalToast.info(t, d),
};
