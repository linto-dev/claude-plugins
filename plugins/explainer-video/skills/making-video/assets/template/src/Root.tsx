import { Composition } from "remotion";
import "./lib/fonts";
import { sceneFolder } from "./lib/video";
import { sample } from "./videos/sample";
// new-video: imports（npm run new-video がこの行の上に足す）

// 動画ごとに 1 つのコンポジション。尺・fps・大きさは calculateMetadata が台本と音声から決める（ここの値は初期値）。
// シーンを 1 つずつ確かめるコンポジションは、sceneFolder で動画ごとの Folder にまとめる。
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="sample"
        component={sample.Video}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={sample.calculateMetadata}
      />
      {sceneFolder(sample)}
      {/* new-video: compositions（npm run new-video がこの行の上に足す） */}
    </>
  );
};
