import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

export interface RikkyoResult {
  rank: number | null;
  wins: number | null;
  losses: number | null;
  points: number | null;
  promotion: '昇級' | '降級' | null;
  note: string;
}

export interface RikkyoPlayer {
  name: string;
  grade: number | null;
  best_result: string | null;
  rank: number | null;
}

export interface BbsMatch {
  opponent: string;
  rikkyo_score: number | null;
  opponent_score: number | null;
  result: '勝ち' | '負け' | '引分';
  round: string | null;
  note: string | null;
  walkover: { win: number; loss: number } | null;
}

export interface BbsPlayer {
  name: string;
  result: string | null;
  wins: number | null;
  losses: number | null;
  board: string | null;
}

export interface KantoTableRow {
  seeding: number;
  team: string;
  scores: (number | null)[];
  wins: number | null;
  points: number | null;
  rank: number | null;  // integer
  promotion: '昇級' | '降級' | null;
}

export interface KantoTable {
  division: string;
  teams: string[];
  team_abbrevs: string[];
  rows: KantoTableRow[];
}

export interface ScheduleDay {
  day: number;
  date: string | null;
  venue: string | null;
}

export interface BbsDetail {
  source_url: string;
  is_official: boolean;
  opponents: string[];
  matches: BbsMatch[];
  players: BbsPlayer[];
  comment: string;
}

export interface Event {
  level: 'regional' | 'national';
  type: 'team' | 'individual';
  name: string;
  division: string | null;
  season_half: 'spring' | 'autumn' | null;
  date: string | null;
  venue: string | null;
  source_url: string;
  source_type: string;
  rikkyo_present: boolean;
  rikkyo_result: RikkyoResult | null;
  rikkyo_players: RikkyoPlayer[];
  national_qualification: string | null;
  bbs_detail: BbsDetail | null;
  kanto_table: KantoTable | null;
  schedule: ScheduleDay[] | null;
  confidence: 'auto' | 'confirmed';
}

export interface SeasonData {
  season: string;
  season_label: string;
  events: Event[];
}

const CONFIRMED_DIR = join(process.cwd(), '..', 'data', 'confirmed');

export async function loadAllSeasons(): Promise<SeasonData[]> {
  let files: string[] = [];
  try {
    files = await readdir(CONFIRMED_DIR);
  } catch {
    return [];
  }

  const seasons: SeasonData[] = [];
  for (const file of files.filter(f => f.endsWith('.json'))) {
    const content = await readFile(join(CONFIRMED_DIR, file), 'utf-8');
    const data = JSON.parse(content) as SeasonData;
    // rikkyo_present=true のイベントのみ表示
    data.events = data.events.filter(e => e.rikkyo_present !== false);
    // 秋季→春季の順(新しいほど上)
    const halfOrder = (h: string | null) => h === 'autumn' ? 0 : h === 'spring' ? 1 : 2;
    data.events.sort((a, b) => halfOrder(a.season_half) - halfOrder(b.season_half));
    seasons.push(data);
  }

  // 年度の新しい順(和暦→令和>平成、数字の降順)
  seasons.sort((a, b) => {
    const rank = (s: string) => {
      const m = s.match(/^(R|H)(\d+)$/i);
      if (!m) return 0;
      const era = m[1].toUpperCase() === 'R' ? 2000 : 1000;
      return era + parseInt(m[2]);
    };
    return rank(b.season) - rank(a.season);
  });

  return seasons;
}

export function isHighlight(event: Event): boolean {
  if (event.type === 'team') {
    const rank = event.rikkyo_result?.rank;
    return rank != null && rank <= 3;
  }
  return (event.rikkyo_players ?? []).some(
    p => p.rank != null && p.rank <= 3 ||
         ['優勝', '準優勝', '第三位'].includes(p.best_result ?? '')
  );
}
