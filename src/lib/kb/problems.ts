// What a big ticket really holds: one row per problem, not per subject line.
// `causes.ts` places a report by tenant and channel. A report the desk read as a one-day move
// (desk-notes.json) is not a day/month swap at all, so it is its own problem here, not a footnote.
import { causeOf, uniqueById, type Report, type Tenant } from '#lib/kb/causes';

export type Problem = 'parser' | 'hint' | 'one-day' | 'unplaced';

export const PROBLEM_TEXT: Record<Problem, string> = {
  parser: 'Shared parser reads day-first dates month first',
  hint: 'booking-v3 form hint says MM/DD, the form reads day first',
  'one-day': 'Date moves by one day across time zones',
  unplaced: 'No tenant on file',
};

export function problemOf(r: Report, t: Tenant | undefined, oneDayMove: readonly string[]): Problem {
  if (oneDayMove.includes(r.id)) return 'one-day';
  return causeOf(r, t) ?? 'unplaced';
}

export type ProblemGroup = {
  problem: Problem;
  reports: Report[];
  // What the desk's own view (CauseTable) counts for this problem. It files one-day moves under
  // their tenant's cause, so `parser` counts them too; `alsoOneDay` says how many.
  deskCount: number;
  alsoOneDay: number;
  tenants: number;
  firstSeen: string;
  lastSeen: string;
  taggedAs: Record<string, number>;
};

export function splitTicket(
  all: Report[],
  ticket: number,
  tenantOf: (r: Report) => Tenant | undefined,
  oneDayMove: readonly string[],
): { merged: number; groups: ProblemGroup[] } {
  const merged = uniqueById(all).filter((r) => r.mergedInto === ticket);
  const by = new Map<Problem, Report[]>();
  for (const r of merged) {
    const p = problemOf(r, tenantOf(r), oneDayMove);
    by.set(p, [...(by.get(p) ?? []), r]);
  }
  const groups = [...by.entries()]
    .map(([problem, rs]) => {
      const days = rs.map((r) => r.receivedAt.slice(0, 10)).sort();
      const filedHere = merged.filter((r) => (causeOf(r, tenantOf(r)) ?? 'unplaced') === problem);
      const alsoOneDay = problem === 'one-day' ? 0 : filedHere.filter((r) => oneDayMove.includes(r.id)).length;
      return {
        problem,
        reports: rs,
        deskCount: problem === 'one-day' ? rs.length : filedHere.length,
        alsoOneDay,
        tenants: new Set(rs.map((r) => r.tenant)).size,
        firstSeen: days[0],
        lastSeen: days[days.length - 1],
        taggedAs: rs.reduce<Record<string, number>>((n, r) => ({ ...n, [r.meta.intakeTag]: (n[r.meta.intakeTag] ?? 0) + 1 }), {}),
      };
    })
    .sort((a, b) => b.deskCount - a.deskCount);
  return { merged: merged.length, groups };
}
