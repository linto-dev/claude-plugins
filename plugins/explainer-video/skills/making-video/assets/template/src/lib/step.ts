// 台本の 1 ステップ（字幕 1 つぶん）。どの動画も同じ形で書く。秒の値は fps に頼らない。
export type Step = {
  /** 画面の下に出す字幕。空文字なら字幕を出さない（表紙など） */
  readonly caption: string;
  /** 読み上げる文。省略すると字幕をそのまま読む。読み違える語だけ読み方で書く */
  readonly say?: string;
  /** 図の動きに要る追加の秒数。字幕を読む時間に足す */
  readonly extra?: number;
  /** 読み終えたあとに置く間（秒）。考える時間のカウントダウンなどに使う */
  readonly hold?: number;
};

/** 台本。キーはシーンのキー（plan.ts の PLAN の key） */
export type Script<K extends string = string> = Record<K, readonly Step[]>;

/** 読み上げの長さ（秒）を足したステップ。シーンはこちらを使う */
export type TimedStep = Step & {
  /** 読み上げ音声の長さ（秒）。音声が無いステップは undefined */
  readonly voice?: number;
};
