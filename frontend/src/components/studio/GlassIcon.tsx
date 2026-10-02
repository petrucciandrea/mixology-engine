import { shapeFor, sliceOutline } from "@/lib/glassShapes";
import type { GlassType } from "@/types/api";

const BASELINE_Y = 226;
const CENTRE_X = 95;

/** Il bicchiere come pittogramma, dalla stessa sagoma del disegno grande:
    si sceglie una forma, e la forma è quella che poi si riempie. */
export function GlassIcon({
  glass,
  isActive,
  size = 30,
}: {
  glass: GlassType;
  isActive: boolean;
  size?: number;
}) {
  const shape = shapeFor(glass === "OTHER" ? null : glass);
  const bowlBottom = BASELINE_Y - shape.stemPx;
  const top = bowlBottom - shape.heightPx;
  const halfSpan = Math.max(shape.widthPx, shape.footPx) / 2 + 4;
  const viewHeight = BASELINE_Y - top + 8;
  const viewWidth = Math.max(halfSpan * 2, viewHeight * 0.72);
  const color = isActive ? "#f79a4d" : "#a9b4ae";
  const stroke = viewHeight / 26;

  return (
    <svg
      viewBox={`${CENTRE_X - viewWidth / 2} ${top - 4} ${viewWidth} ${viewHeight}`}
      width={size}
      height={size}
      aria-hidden
      className="block"
    >
      <path
        d={sliceOutline(shape, 0, 1, CENTRE_X, bowlBottom)}
        fill={isActive ? "rgba(232,129,43,.28)" : "none"}
        stroke={color}
        strokeWidth={stroke}
        strokeLinejoin="round"
      />
      {shape.stemPx > 0 && (
        <>
          <line
            x1={CENTRE_X}
            x2={CENTRE_X}
            y1={bowlBottom}
            y2={BASELINE_Y}
            stroke={color}
            strokeWidth={stroke}
          />
          <line
            x1={CENTRE_X - shape.footPx / 2}
            x2={CENTRE_X + shape.footPx / 2}
            y1={BASELINE_Y}
            y2={BASELINE_Y}
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
          />
        </>
      )}
    </svg>
  );
}
