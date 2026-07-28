import { useRef, useState, useCallback } from "react";

export type DragState = {
  email: string;
  x: number;
  y: number;
  targetEmail: string | null;
  targetX: number;
  targetY: number;
};

export type DragResult = {
  type: "move" | "disconnect" | "none";
  email: string;
  targetEmail?: string;
};

const DRAG_THRESHOLD = 6;

export function useDragCard(onDragEnd: (result: DragResult) => void) {
  const [drag, setDrag] = useState<DragState | null>(null);
  const onDragEndRef = useRef(onDragEnd);
  onDragEndRef.current = onDragEnd;

  const findTarget = useCallback((cx: number, cy: number, srcEmail: string): { email: string; x: number; y: number } | null => {
    for (const el of document.elementsFromPoint(cx, cy)) {
      const card = (el as HTMLElement).closest?.("[data-email]");
      if (card) {
        const em = card.getAttribute("data-email");
        if (em && em !== srcEmail) {
          const rect = card.getBoundingClientRect();
          return { email: em, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        }
      }
    }
    return null;
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent, email: string) => {
    e.stopPropagation();
    e.preventDefault();

    const startX = e.clientX;
    const startY = e.clientY;
    let isActive = false;
    let currentTarget: string | null = null;

    const handleMove = (ev: PointerEvent) => {
      const dx = Math.abs(ev.clientX - startX);
      const dy = Math.abs(ev.clientY - startY);
      if (!isActive && (dx > DRAG_THRESHOLD || dy > DRAG_THRESHOLD)) {
        isActive = true;
      }
      if (!isActive) return;

      const hit = findTarget(ev.clientX, ev.clientY, email);
      currentTarget = hit?.email || null;

      document.querySelectorAll<HTMLElement>(".cz-ot-card--drop-target").forEach(c =>
        c.classList.remove("cz-ot-card--drop-target")
      );
      if (hit) {
        const card = document.querySelector<HTMLElement>(`[data-email="${hit.email}"]`);
        card?.classList.add("cz-ot-card--drop-target");
      }

      setDrag({
        email,
        x: ev.clientX,
        y: ev.clientY,
        targetEmail: hit?.email || null,
        targetX: hit?.x || 0,
        targetY: hit?.y || 0,
      });
    };

    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);

      document.querySelectorAll<HTMLElement>(".cz-ot-card--drop-target").forEach(c =>
        c.classList.remove("cz-ot-card--drop-target")
      );

      setDrag(null);

      if (!isActive) {
        onDragEndRef.current({ type: "none", email });
      } else if (currentTarget) {
        onDragEndRef.current({ type: "move", email, targetEmail: currentTarget });
      } else {
        onDragEndRef.current({ type: "disconnect", email });
      }
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  }, [findTarget]);

  return { drag, onPointerDown };
}
