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

/** 年度キー(H21/R08等)を比較可能な数値にする。令和>平成、数字昇順。 */
function seasonSortRank(s: string): number {
  const m = s.match(/^(R|H)(\d+)$/i);
  if (!m) return 0;
  const era = m[1].toUpperCase() === 'R' ? 2000 : 1000;
  return era + parseInt(m[2]);
}

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
  seasons.sort((a, b) => seasonSortRank(b.season) - seasonSortRank(a.season));

  return seasons;
}

// ==== 現役団体戦 昇降級推移(LeagueTrend)用の集計 ====

// 級の正規化テーブル。
// 関東学生団体戦のリーグは下から C2 < C1 < B2 < B1 < A の5段階。
// 縦軸数値(level)は下位=小・上位=大 に割り当てる(C2=1 … A=5)。
//
// 【単一「C級」時代(H21〜H22)の扱い ― 実データに基づく判断】
//   H21春・H22秋のデータは division="C級"(C1/C2 に分割される前の単一クラス)。
//   実データ上、立教は H22秋「C級」→ H23春「C2級」へ昇降級の記録なしに連続移動しており、
//   分割後の最下位クラス C2 と地続きである。したがって旧「C級」は C2 と同じ level=1 とみなす。
//   表示ラベルは実態に合わせ "C" とし、生の division 値はツールチップ側で補足する。
// 【表記ゆれ】
//   R08春は "B級2組"(= B2級 の別表記)。"B級1組"="B1級" 等も含め表記ゆれをここで吸収する。
const DIVISION_TABLE: Record<string, { level: number; label: string }> = {
  'A級':    { level: 5, label: 'A' },
  'B1級':   { level: 4, label: 'B1' },
  'B級1組': { level: 4, label: 'B1' },
  'B2級':   { level: 3, label: 'B2' },
  'B級2組': { level: 3, label: 'B2' },
  'C1級':   { level: 2, label: 'C1' },
  'C級1組': { level: 2, label: 'C1' },
  'C2級':   { level: 1, label: 'C2' },
  'C級2組': { level: 1, label: 'C2' },
  'C級':    { level: 1, label: 'C' },  // 分割前の単一C級 → C2相当(上記コメント参照)
};

/** 縦軸の数値 → リーグ名ラベル(y軸目盛りの表示に使う) */
export const LEAGUE_AXIS_LABELS: Record<number, string> = {
  1: 'C2', 2: 'C1', 3: 'B2', 4: 'B1', 5: 'A',
};

export interface LeagueTrendPoint {
  season: string;                        // "H21"
  season_half: 'spring' | 'autumn';
  label: string;                         // "H21春"
  division: string;                      // 生の値 "C級" "B級2組" 等
  division_label: string;                // 正規化ラベル "C2" 等
  level: number;                         // 縦軸数値 1..5
  rank: number | null;
  promotion: '昇級' | '降級' | null;
  champion: boolean;                     // rank===1(優勝)
}

/**
 * 時系列スロット。point===null はデータの無い半期(R02=コロナ 等)。
 * 描画側(LeagueTrend.astro)は現在この区間を直線で繋いで表示する(spanGaps:true)。
 * マーカーは置かれないため、null スロットは x軸ラベルとしてのみ現れる。
 */
export interface LeagueTrendSlot {
  season: string;
  season_half: 'spring' | 'autumn';
  label: string;
  point: LeagueTrendPoint | null;
}

const halfLabel = (h: 'spring' | 'autumn') => (h === 'spring' ? '春' : '秋');

/**
 * type:'team' かつ立教が登場するイベントから、シーズン別の所属リーグを時系列化する。
 * 各年度の春/秋の全スロットを古い順に並べ、団体戦の結果が無い半期は point=null にする。
 * 両端のデータ無し期間(範囲外)は軸に含めない。
 * seasons を渡せば再読み込みせずに集計する(省略時は loadAllSeasons() を呼ぶ)。
 */
export async function loadLeagueTrend(seasons?: SeasonData[]): Promise<LeagueTrendSlot[]> {
  seasons ??= await loadAllSeasons();
  // loadAllSeasons は新しい順に整列済みなので、反転して古い順(H21春 →)にする
  const ordered = [...seasons].sort((a, b) => seasonSortRank(a.season) - seasonSortRank(b.season));

  // (season, half) -> その半期の主たる団体戦の順位
  const points = new Map<string, LeagueTrendPoint>();
  for (const s of ordered) {
    for (const e of s.events) {
      if (e.type !== 'team' || !e.rikkyo_present) continue;
      if (e.division == null || e.season_half == null) continue;
      const rr = e.rikkyo_result;
      if (!rr || rr.rank == null) continue;   // 順位のある本結果のみ(「N日目結果」等は除外)
      const norm = DIVISION_TABLE[e.division];
      if (!norm) continue;                     // 未知の級表記はテーブル追加まで集計対象外
      const key = `${s.season}:${e.season_half}`;
      if (points.has(key)) continue;           // 同一半期に複数該当したら先勝ち
      points.set(key, {
        season: s.season,
        season_half: e.season_half,
        label: `${s.season}${halfLabel(e.season_half)}`,
        division: e.division,
        division_label: norm.label,
        level: norm.level,
        rank: rr.rank,
        promotion: rr.promotion,
        champion: rr.rank === 1,
      });
    }
  }

  // 全年度を 春→秋 で展開(欠測の可視化のため、データの無い半期も軸に残す)
  const allSlots: Omit<LeagueTrendSlot, 'point'>[] = [];
  for (const s of ordered) {
    for (const half of ['spring', 'autumn'] as const) {
      allSlots.push({ season: s.season, season_half: half, label: `${s.season}${halfLabel(half)}` });
    }
  }

  const hasData = (slot: { season: string; season_half: string }) =>
    points.has(`${slot.season}:${slot.season_half}`);
  const first = allSlots.findIndex(hasData);
  if (first === -1) return [];
  let last = allSlots.length - 1;
  while (last > first && !hasData(allSlots[last])) last--;

  return allSlots.slice(first, last + 1).map(slot => ({
    ...slot,
    point: points.get(`${slot.season}:${slot.season_half}`) ?? null,
  }));
}

// ==== 社団戦(東将連)データ ====
// 関東学生団体戦とは名前空間を分離(data/shadan/**)。個人成績は非公開のため読み込まない。

export interface ShadanLeagueTableRow {
  seeding: number;
  team: string;
  scores: (number | null)[];
  wins: number | null;
  points: number | null;
  rank: number | null;
  promotion: '昇級' | '降級' | null;
}

export interface ShadanLeagueTable {
  division: string;
  teams: string[];
  team_abbrevs?: string[];
  rows: ShadanLeagueTableRow[];
}

export interface ShadanTeam {
  team_id: string;
  team_name: string;
  kai: number;
  division: string;
  rank: number | null;
  points: number | null;
  wins: number | null;
  promotion: '昇級' | '降級' | null;
  source_type: string;
  source_url: string;
  league_table: ShadanLeagueTable | null;
  note?: string;
}

export interface ShadanSeason {
  kai: number;
  season: string;
  season_label: string;
  source?: {
    hub_url?: string;
    ichiran_pdf?: string;
    league_pdf?: string[];
  };
  teams: ShadanTeam[];
}

const SHADAN_CONFIRMED_DIR = join(process.cwd(), '..', 'data', 'shadan', 'confirmed');

/** 社団戦の年度別データを新しい回(kai)順に返す。ディレクトリが無ければ空配列。 */
export async function loadShadanSeasons(): Promise<ShadanSeason[]> {
  let files: string[] = [];
  try {
    files = await readdir(SHADAN_CONFIRMED_DIR);
  } catch {
    return [];
  }
  const seasons: ShadanSeason[] = [];
  for (const file of files.filter(f => f.endsWith('.json'))) {
    const content = await readFile(join(SHADAN_CONFIRMED_DIR, file), 'utf-8');
    seasons.push(JSON.parse(content) as ShadanSeason);
  }
  seasons.sort((a, b) => b.kai - a.kai);
  return seasons;
}

// 個人レーティング推移(公開同意者のみコミットされる。ROADMAP §2-2)
export interface ShadanPlayerPoint {
  kai: number;
  season: string;
  season_label: string;
  team: string;
  division: string | null;
  rating: number;
  games: number;
  source_url: string;
}

export interface ShadanPlayer {
  player_id: string;
  name: string;
  /** 内部キー。ページには表示しない */
  reg_no: number;
  consent: string;
  history: ShadanPlayerPoint[];
}

const SHADAN_PLAYERS_DIR = join(process.cwd(), '..', 'data', 'shadan', 'players');

/** 公開同意済みの個人レーティング推移を返す。ディレクトリが無ければ空配列。 */
export async function loadShadanPlayers(): Promise<ShadanPlayer[]> {
  let files: string[] = [];
  try {
    files = await readdir(SHADAN_PLAYERS_DIR);
  } catch {
    return [];
  }
  const players: ShadanPlayer[] = [];
  for (const file of files.filter(f => f.endsWith('.json'))) {
    const content = await readFile(join(SHADAN_PLAYERS_DIR, file), 'utf-8');
    const p = JSON.parse(content) as ShadanPlayer;
    p.history.sort((a, b) => a.kai - b.kai);
    players.push(p);
  }
  players.sort((a, b) => a.player_id.localeCompare(b.player_id));
  return players;
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
