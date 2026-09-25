import { useEffect, useMemo, useRef, useState } from "react";
import type { Cell, WorkbookView } from "../lib/types";

export interface GridChange {
  edits: Record<string, Record<string, string>>;
  fieldValues: Record<string, string>;
}

interface SpreadsheetEditorProps {
  view: WorkbookView;
  onChange: (change: GridChange) => void;
}

// --- address + numeric helpers --- //
function colToNum(letters: string): number {
  let n = 0;
  for (const ch of letters.toUpperCase()) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n;
}
function numToCol(n: number): string {
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}
function parseAddr(addr: string): { col: number; row: number } | null {
  const m = /^([A-Z]+)([0-9]+)$/i.exec(addr);
  if (!m) return null;
  return { col: colToNum(m[1]), row: parseInt(m[2], 10) };
}
function toNum(v: unknown): number {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = parseFloat(v);
    return Number.isNaN(n) ? 0 : n;
  }
  return 0;
}

export function SpreadsheetEditor({ view, onChange }: SpreadsheetEditorProps) {
  const [activeSheet, setActiveSheet] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  // Edited cells only: sheetName -> { ADDR -> raw string }.
  const [overrides, setOverrides] = useState<Record<string, Record<string, string>>>({});

  const sheet = view.sheets[activeSheet];
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const { cellIndex, addressToField } = useMemo(() => {
    const idx = new Map<string, Cell>();
    sheet.rows.forEach((row) => row.forEach((c) => idx.set(c.address.toUpperCase(), c)));
    const a2f = new Map<string, string>();
    view.fields.forEach((f) => {
      if (f.sheet === sheet.name && f.cell) a2f.set(f.cell.toUpperCase(), f.id);
    });
    return { cellIndex: idx, addressToField: a2f };
  }, [sheet, view.fields]);

  const originalString = (cell: Cell | undefined): string => {
    if (!cell) return "";
    if (cell.formula) return cell.formula;
    return cell.value === null || cell.value === undefined ? "" : String(cell.value);
  };

  const rawAt = (sheetName: string, addr: string): string => {
    const ov = overrides[sheetName]?.[addr.toUpperCase()];
    if (ov !== undefined) return ov;
    if (sheetName === sheet.name) return originalString(cellIndex.get(addr.toUpperCase()));
    return "";
  };

  // --- formula evaluation (best-effort, same-sheet references) --- //
  const cellNumber = (addr: string, visited: Set<string>): number => {
    const key = addr.toUpperCase();
    if (visited.has(key)) return 0;
    visited.add(key);
    const raw = rawAt(sheet.name, key);
    if (typeof raw === "string" && raw.startsWith("=")) return evalFormula(raw, visited);
    return toNum(raw);
  };

  const expandArgs = (argStr: string, visited: Set<string>): number[] => {
    const out: number[] = [];
    for (const part of argStr.split(",")) {
      const arg = part.trim();
      const range = /^([A-Z]+[0-9]+):([A-Z]+[0-9]+)$/i.exec(arg);
      if (range) {
        const a = parseAddr(range[1])!;
        const b = parseAddr(range[2])!;
        for (let r = Math.min(a.row, b.row); r <= Math.max(a.row, b.row); r++)
          for (let c = Math.min(a.col, b.col); c <= Math.max(a.col, b.col); c++)
            out.push(cellNumber(`${numToCol(c)}${r}`, visited));
      } else if (/^[A-Z]+[0-9]+$/i.test(arg)) {
        out.push(cellNumber(arg, visited));
      } else if (arg !== "") {
        out.push(toNum(arg));
      }
    }
    return out;
  };

  const evalFormula = (formula: string, visited: Set<string>): number => {
    try {
      let expr = formula.replace(/^=/, "");
      expr = expr.replace(/(SUM|AVERAGE|MIN|MAX|COUNT)\(([^)]*)\)/gi, (_m, fn, args) => {
        const nums = expandArgs(args, new Set(visited));
        const f = String(fn).toUpperCase();
        if (f === "SUM") return String(nums.reduce((s, n) => s + n, 0));
        if (f === "AVERAGE") return String(nums.length ? nums.reduce((s, n) => s + n, 0) / nums.length : 0);
        if (f === "MIN") return String(nums.length ? Math.min(...nums) : 0);
        if (f === "MAX") return String(nums.length ? Math.max(...nums) : 0);
        return String(nums.length);
      });
      expr = expr.replace(/[A-Z]+[0-9]+/gi, (ref) => String(cellNumber(ref, new Set(visited))));
      return evalArithmetic(expr);
    } catch {
      return 0;
    }
  };

  const display = (addr: string): string => {
    const raw = rawAt(sheet.name, addr);
    if (typeof raw === "string" && raw.startsWith("=")) {
      const n = evalFormula(raw, new Set());
      return Number.isInteger(n) ? String(n) : n.toFixed(2);
    }
    return raw;
  };

  // Emit edits + current field values whenever a cell changes.
  useEffect(() => {
    const fieldValues: Record<string, string> = {};
    view.fields.forEach((f) => {
      if (f.sheet && f.cell) fieldValues[f.id] = rawAt(f.sheet, f.cell.toUpperCase());
    });
    onChangeRef.current({ edits: overrides, fieldValues });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overrides]);

  const setCell = (addr: string, value: string) => {
    setOverrides((prev) => {
      const forSheet = { ...(prev[sheet.name] ?? {}) };
      forSheet[addr.toUpperCase()] = value;
      return { ...prev, [sheet.name]: forSheet };
    });
  };

  const focusCell = (r: number, c: number) => {
    const el = document.getElementById(`c-${activeSheet}-${r}-${c}`);
    if (el) (el as HTMLInputElement).focus();
  };

  const cols = Array.from({ length: sheet.n_cols }, (_, i) => numToCol(i + 1));

  return (
    <div className="card overflow-hidden">
      {view.sheets.length > 1 && (
        <div className="flex gap-1 border-b border-slate-200 bg-slate-50 px-2 pt-2">
          {view.sheets.map((s, i) => (
            <button
              key={s.name}
              onClick={() => setActiveSheet(i)}
              className={`rounded-t-lg px-3 py-1.5 text-sm font-medium ${
                i === activeSheet ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
      <div className="max-h-[70vh] overflow-auto">
        <table className="border-collapse text-sm">
          <thead className="sticky top-0 z-20">
            <tr>
              <th className="sticky left-0 z-30 h-8 w-12 border border-slate-200 bg-slate-100" />
              {cols.map((c) => (
                <th
                  key={c}
                  className="h-8 min-w-[7rem] border border-slate-200 bg-slate-100 px-2 text-xs font-semibold text-slate-500"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.rows.map((row, ri) => (
              <tr key={ri}>
                <td className="sticky left-0 z-10 h-9 w-12 border border-slate-200 bg-slate-100 text-center text-xs font-semibold text-slate-500">
                  {ri + 1}
                </td>
                {row.map((cell, ci) => {
                  const addr = cell.address.toUpperCase();
                  const key = `${sheet.name}!${addr}`;
                  const isField = addressToField.has(addr);
                  const isEditing = editing === key;
                  const value = isEditing ? rawAt(sheet.name, addr) : display(addr);
                  return (
                    <td
                      key={cell.address}
                      className={`border p-0 ${isField ? "border-brand-300 bg-brand-50/60" : "border-slate-200"}`}
                    >
                      <input
                        id={`c-${activeSheet}-${ri}-${ci}`}
                        value={value}
                        onFocus={() => setEditing(key)}
                        onBlur={() => setEditing((k) => (k === key ? null : k))}
                        onChange={(e) => setCell(addr, e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            focusCell(ri + 1, ci);
                          }
                        }}
                        aria-label={`Cell ${cell.address}`}
                        className="h-9 w-full bg-transparent px-2 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500"
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
        Edit any cell like a spreadsheet. Type{" "}
        <code className="rounded bg-slate-200 px-1">=SUM(A1:A3)</code> for formulas. Highlighted cells
        are the ones being assessed. Press Enter to move down.
      </div>
    </div>
  );
}

// A tiny, safe arithmetic evaluator (no eval): shunting-yard for + - * / ( ).
function evalArithmetic(expr: string): number {
  const tokens = expr.match(/(\d+\.?\d*|\.\d+|[+\-*/()])/g);
  if (!tokens) return 0;
  const output: (number | string)[] = [];
  const ops: string[] = [];
  const prec: Record<string, number> = { "+": 1, "-": 1, "*": 2, "/": 2 };
  for (const t of tokens) {
    if (/^[\d.]+$/.test(t)) {
      output.push(parseFloat(t));
    } else if (t === "(") {
      ops.push(t);
    } else if (t === ")") {
      while (ops.length && ops[ops.length - 1] !== "(") output.push(ops.pop()!);
      ops.pop();
    } else {
      while (ops.length && prec[ops[ops.length - 1]] >= prec[t]) output.push(ops.pop()!);
      ops.push(t);
    }
  }
  while (ops.length) output.push(ops.pop()!);

  const stack: number[] = [];
  for (const t of output) {
    if (typeof t === "number") {
      stack.push(t);
    } else {
      const b = stack.pop() ?? 0;
      const a = stack.pop() ?? 0;
      stack.push(t === "+" ? a + b : t === "-" ? a - b : t === "*" ? a * b : b === 0 ? 0 : a / b);
    }
  }
  return stack[0] ?? 0;
}
