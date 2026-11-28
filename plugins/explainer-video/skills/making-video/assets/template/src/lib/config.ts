// 動画の画面の大きさとフレームレート。src/Root.tsx の <Composition> と、scripts/ の計算が使う。
// node からも読むので、このファイルは "@/" の別名と JSX を使わない（src/lib/timing.ts・timeline.ts・step.ts も同じ）。
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const FPS = 30;
