// シーン。型（@/parts/templates）に収まるものは型を使い、収まらないものは SceneFrame の中に図を直接書く（what）。
// 座標は 1920×1080。図は CONTENT（上 177・下 807・左右 96）の中に置く。
import type React from "react";
import { useSteps } from "@/lib/anim";
import { CONTENT, SceneFrame } from "@/parts/frame";
import { Box, Chip, LabeledArrow, Place } from "@/parts/graphics";
import { DataTable } from "@/parts/table";
import {
  AgendaScene,
  ListScene,
  PointsScene,
  QuestionScene,
  SourcesScene,
  ThinkScene,
  TitleScene,
} from "@/parts/templates";
import { kit } from "./kit";
import type { SceneKey } from "./plan";
import { VIDEO } from "./plan";
import { VOICE_CREDIT } from "./voice";

const Title: React.FC = () => (
  <TitleScene
    frame={kit.frameOf("title")}
    kicker="explainer-video の見本"
    title={VIDEO.title}
    subtitle={VIDEO.subtitle}
    source={VIDEO.source}
  />
);

const Agenda: React.FC = () => (
  <AgendaScene
    frame={kit.frameOf("agenda")}
    items={[
      { label: "1", title: "ハッシュ値とは" },
      { label: "2", title: "考えてみよう：改ざんの確かめ方" },
      { label: "まとめ", title: "要点のふり返り" },
    ]}
  />
);

// ファイル → ハッシュ関数 → ハッシュ値。2 段目で 1 文字変えた入力の値を比べる。
const ROW1 = 300;
const ROW2 = 600;
const What: React.FC = () => {
  const f = kit.frameOf("what");
  const { p } = useSteps(f.steps);
  const row = (
    y: number,
    input: string,
    value: string,
    show: number,
    changed: boolean,
  ) => (
    <>
      <Box
        x={CONTENT.left}
        y={y - 75}
        w={420}
        h={150}
        p={show}
        hi={changed ? 1 : 0}
        tone="vermillion"
      >
        <div className="text-base text-muted-foreground">入力</div>
        <div className="font-mono">{input}</div>
      </Box>
      <LabeledArrow
        from={{ x: CONTENT.left + 435, y }}
        to={{ x: 750, y }}
        p={show}
      />
      <Box x={765} y={y - 60} w={330} h={120} p={show}>
        ハッシュ関数
        <div className="text-base text-muted-foreground">SHA-256</div>
      </Box>
      <LabeledArrow from={{ x: 1110, y }} to={{ x: 1260, y }} p={show} />
      <Place x={1275} y={y} anchor="left" opacity={show}>
        <Chip tone={changed ? "vermillion" : "blue"} size="xl" mono>
          {value}
        </Chip>
      </Place>
    </>
  );
  return (
    <SceneFrame {...f}>
      {row(ROW1, "合計 1,000 円", "628ac205 1a44dd20 …", p(0, 0.2, 0.8), false)}
      <Place x={1275} y={ROW1 + 78} anchor="left" opacity={p(1, 0.2)}>
        <span className="text-xl font-bold text-figure-blue-text">
          いつも 256 ビット（16 進数で 64 桁）
        </span>
      </Place>
      {row(ROW2, "合計 9,000 円", "ddb32449 33a1fbe2 …", p(2, 0.2, 0.8), true)}
      <Place x={CONTENT.left + 210} y={ROW2 + 108} opacity={p(2, 0.6)}>
        <span className="text-base font-bold text-figure-vermillion-text">
          1 文字だけ変えた
        </span>
      </Place>
    </SceneFrame>
  );
};

// 左に性質を積み、右の表で「同じ入力 → 同じ値」「違う入力 → 違う値」を示す
const Traits: React.FC = () => (
  <PointsScene
    frame={kit.frameOf("traits")}
    items={[
      { step: 0, head: "決まった値", text: "同じ入力からは、いつも{{同じ値}}" },
      {
        step: 1,
        head: "わずかな違いも出る",
        text: "少しでも違えば、{{まったく違う値}}",
      },
      {
        step: 2,
        head: "元に戻せない",
        text: "値から{{元の入力は割り出せない}}",
      },
    ]}
    side={({ p, between }) => (
      <DataTable
        head={["入力", "ハッシュ値（先頭 8 桁）"]}
        rows={[
          ["合計 1,000 円", "``628ac205``"],
          ["合計 1,000 円", "``628ac205``"],
          ["合計 9,000 円", "``ddb32449``"],
        ]}
        focus={{ 0: between(0, 1), 1: between(0, 1), 2: between(1, 2) }}
        focusTone="blue"
        dim={0.5 * (p(0) - p(2))}
        width={840}
        style={{ position: "absolute", left: 984, top: CONTENT.top + 12 }}
      />
    )}
  />
);

const Q1: React.FC = () => (
  <QuestionScene
    frame={kit.frameOf("q1")}
    tag="問い"
    question="ダウンロードしたファイルが{{改ざんされていない}}ことを、どう確かめるか"
    kind="手順を答える"
    kindStep={1}
  />
);

const Q1Think: React.FC = () => (
  <ThinkScene
    frame={kit.frameOf("q1think")}
    items={[
      { step: 0, label: "配布元が公開しているハッシュ値を確かめる" },
      { step: 1, label: "手元のファイルからハッシュ値を計算する" },
      {
        step: 2,
        label: "同じ場所の値は、ファイルと一緒に差し替えられうる",
        kind: "pitfall",
      },
      { step: 3, label: "別の信頼できる経路（公式サイトなど）で値を得る" },
      { step: 4, label: "2 つの値を比べる" },
    ]}
    answer="別の経路で得た値と一致を確かめる"
    answerLabel="答え"
    answerStep={4}
    answerAt={{ x: 1340, y: 480 }}
    answerSize="2xl"
  />
);

const Summary: React.FC = () => (
  <ListScene
    frame={kit.frameOf("summary")}
    items={[
      "ハッシュ値は、データから作る決まった長さの短い値",
      "中身が少しでも変われば値が変わるので、改ざんに気付ける",
      "比べる値は、ファイルとは別の信頼できる経路で手に入れる",
    ]}
  />
);

const Sources: React.FC = () => (
  <SourcesScene
    frame={kit.frameOf("sources")}
    entries={[
      {
        label: "規格",
        title: "FIPS 180-4 Secure Hash Standard（NIST）",
        meta: "SHA-256",
      },
    ]}
    footer={[VIDEO.source, `音声：${VOICE_CREDIT}`]}
  />
);

export const SCENES: Partial<Record<SceneKey, React.FC>> = {
  title: Title,
  agenda: Agenda,
  what: What,
  traits: Traits,
  q1: Q1,
  q1think: Q1Think,
  summary: Summary,
  sources: Sources,
};
