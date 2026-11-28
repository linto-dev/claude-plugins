# このプロジェクトでの作業

原稿から解説動画を作る Remotion のプロジェクト。explainer-video プラグインの雛形から作った。コマンドとファイルの役目は [README.md](README.md)、見た目の決まりは [DESIGN.md](DESIGN.md) にある。

- 動画を作る・直す流れは、explainer-video プラグインのスキル（`/explainer-video:making-video` から始める）に従う。プラグインが無い環境では README の「コマンド」の順に進める
- シーンや部品を書く前に DESIGN.md を読む。Remotion の API は公式のスキル（`.claude/skills/remotion-*`）で確かめる。DESIGN.md の「Remotion 公式のスキルとの関係」の 2 点だけは公式と違う
- `src/videos/<slug>/plan.ts`・`script.ts`・`voice.ts` と `src/lib/config.ts`・`step.ts`・`timing.ts`・`timeline.ts` は node（`scripts/`）からも読む。`"@/"` の別名と JSX を使わず、相対パスに `.ts` を付けて読む
- `voice.ts` と `STORYBOARD.md` は生成物。手で直さず、`npm run voice`・`npm run storyboard` で作り直す
- 変えたら `npm run lint` を通す。整形は `npm run check`（ほかの人やセッションが同じプロジェクトを触っているときは、`npx biome check --write src/videos/<slug>` のように自分のフォルダに限る）
- `src/Root.tsx` と README の動画の表は、ほかの動画と共有する。足すときは直前に読み直し、自分の行だけを足す
- VOICEVOX のユーザー辞書はエンジンの中で共有される。同じ表記の語は、ほかの動画と同じ読みとアクセントにする
